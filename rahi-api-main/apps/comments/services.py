from typing import List, Dict, Optional, Tuple
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Q, Prefetch
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from apps.comments.models import Comment, CommentReaction, CommentModerationLog
from apps.project.models import Project


class CommentService:
    """
    Service class for comment-related business logic.
    Handles complex operations, caching, and integrations.
    """
    
    @staticmethod
    def get_comments_for_object(content_type_str: str, object_id, user=None, include_pending: bool=False) -> List[Comment]:
        object_id = str(object_id)  # <— key change
        try:
            app_label, model = content_type_str.split('.')
            content_type = ContentType.objects.get(app_label=app_label, model=model)
        except (ValueError, ContentType.DoesNotExist):
            return []

        cache_key = f"comments:{content_type.id}:{object_id}:approved"
        if not include_pending:
            cached_comments = cache.get(cache_key)
            if cached_comments is not None:
                return cached_comments
        
        # Build queryset with optimizations
        queryset = Comment.objects.select_related('user','approved_by')\
            .prefetch_related(
                Prefetch('replies', queryset=Comment.objects.filter(status='APPROVED').select_related('user'), to_attr='approved_replies'),
                'reactions'
            ).filter(content_type=content_type, object_id=object_id, parent__isnull=True)
        if not include_pending or not (user and hasattr(user, 'role') and user.role == 0):
            queryset = queryset.filter(status='APPROVED')
        comments = list(queryset.order_by('-created_at'))
        if not include_pending:
            cache.set(cache_key, comments, timeout=300)
        return comments
    
    @staticmethod
    def create_comment(user, content_type_str: str, object_id: int, 
                      content: str, parent_id: Optional[int] = None) -> Tuple[Comment, bool]:
        object_id = str(object_id)
        try:
            app_label, model = content_type_str.split('.')
            content_type = ContentType.objects.get(app_label=app_label, model=model)
        except (ValueError, ContentType.DoesNotExist):
            raise ValueError("نوع محتوای نامعتبر")
        
        # Validate target object exists
        try:
            target_object = content_type.get_object_for_this_type(id=object_id)
        except:
            raise ValueError("آبجکت مورد نظر یافت نشد")
        
        # Validate parent comment if provided
        parent_comment = None
        if parent_id:
            try:
                parent_comment = Comment.objects.get(
                    id=parent_id,
                    content_type=content_type,
                    object_id=object_id,
                    status='APPROVED'
                )
                if parent_comment.parent is not None:
                    raise ValueError("نمی‌توان به پاسخ‌ها پاسخ داد")
            except Comment.DoesNotExist:
                raise ValueError("نظر والد یافت نشد")
        
        # Create comment
        with transaction.atomic():
            comment = Comment.objects.create(
                user=user,
                content_type=content_type,
                object_id=object_id,
                content=content.strip(),
                parent=parent_comment
            )
            
            # Update parent replies count if this is a reply
            if parent_comment:
                parent_comment.replies_count = parent_comment.replies.filter(
                    status='APPROVED'
                ).count()
                parent_comment.save(update_fields=['replies_count'])
            
            # Invalidate cache
            CommentService.invalidate_comments_cache(content_type_str, object_id)
        
        return comment, True
    
    @staticmethod
    def add_reaction(user, comment_id: int, reaction_type: str) -> Tuple[str, Comment]:
        """
        Add or update user reaction to a comment.
        
        Returns:
            Tuple of (message, updated_comment)
        """
        if reaction_type not in ['LIKE', 'DISLIKE']:
            raise ValueError("نوع واکنش باید LIKE یا DISLIKE باشد")
        
        try:
            comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            raise ValueError("نظر یافت نشد")
        
        with transaction.atomic():
            reaction, created = CommentReaction.objects.get_or_create(
                comment=comment,
                user=user,
                defaults={'reaction_type': reaction_type}
            )
            
            if not created:
                if reaction.reaction_type == reaction_type:
                    # Same reaction clicked - remove it
                    reaction.delete()
                    message = "واکنش حذف شد"
                else:
                    # Different reaction - update it
                    reaction.reaction_type = reaction_type
                    reaction.save()
                    message = "واکنش به‌روزرسانی شد"
            else:
                message = "واکنش اضافه شد"
            
            # Refresh comment to get updated counts
            comment.refresh_from_db()
        
        return message, comment
    
    @staticmethod
    def bulk_moderate_comments(comment_ids: List[int], action: str, 
                             moderator, reason: str = "") -> int:
        """
        Perform bulk moderation actions on comments.
        
        Args:
            comment_ids: List of comment IDs
            action: 'approve', 'reject', or 'delete'
            moderator: User performing the action
            reason: Optional reason for the action
            
        Returns:
            Number of successfully processed comments
        """
        if action not in ['approve', 'reject', 'delete']:
            raise ValueError("عملیات نامعتبر")
        
        comments = Comment.objects.filter(id__in=comment_ids)
        success_count = 0
        
        with transaction.atomic():
            for comment in comments:
                processed = False
                
                if action == 'approve' and comment.status != 'APPROVED':
                    comment.approve(moderator)
                    processed = True
                elif action == 'reject' and comment.status != 'REJECTED':
                    comment.reject(moderator)
                    processed = True
                elif action == 'delete':
                    processed = True
                
                if processed:
                    # Log the action
                    CommentModerationLog.objects.create(
                        comment=comment,
                        moderator=moderator,
                        action=action.upper(),
                        reason=reason
                    )
                    success_count += 1
                    
                    # Invalidate related caches
                    content_type_str = f"{comment.content_type.app_label}.{comment.content_type.model}"
                    CommentService.invalidate_comments_cache(content_type_str, comment.object_id)
            
            # Delete comments if needed (after logging)
            if action == 'delete':
                comments.delete()
        
        return success_count
    
    @staticmethod
    def get_comment_statistics(content_type_str: str = None, 
                             object_id: int = None) -> Dict:
        """
        Get comprehensive comment statistics.
        
        Args:
            content_type_str: Optional filter by content type
            object_id: Optional filter by object ID
        """
        queryset = Comment.objects.all()
        
        # Apply filters if provided
        if content_type_str and object_id:
            try:
                app_label, model = content_type_str.split('.')
                content_type = ContentType.objects.get(app_label=app_label, model=model)
                queryset = queryset.filter(content_type=content_type, object_id=object_id)
            except (ValueError, ContentType.DoesNotExist):
                pass
        
        # Calculate statistics
        stats = queryset.aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='APPROVED')),
            pending=Count('id', filter=Q(status='PENDING')),
            rejected=Count('id', filter=Q(status='REJECTED')),
            total_likes=Count('reactions', filter=Q(reactions__reaction_type='LIKE')),
            total_dislikes=Count('reactions', filter=Q(reactions__reaction_type='DISLIKE')),
            total_replies=Count('id', filter=Q(parent__isnull=False))
        )
        
        # Add percentage calculations
        if stats['total'] > 0:
            stats['approval_rate'] = round((stats['approved'] / stats['total']) * 100, 2)
            stats['pending_rate'] = round((stats['pending'] / stats['total']) * 100, 2)
        else:
            stats['approval_rate'] = 0
            stats['pending_rate'] = 0
        
        return stats
    
    @staticmethod
    def get_trending_comments(content_type_str: str = None, days: int = 7) -> List[Comment]:
        """
        Get trending comments based on recent activity.
        
        Args:
            content_type_str: Optional filter by content type
            days: Number of days to look back
        """
        since_date = timezone.now() - timedelta(days=days)
        
        queryset = Comment.objects.filter(
            status='APPROVED',
            created_at__gte=since_date
        ).annotate(
            total_reactions=Count('reactions'),
            like_ratio=Count('reactions', filter=Q(reactions__reaction_type='LIKE'))
        ).select_related('user', 'content_type')
        
        # Filter by content type if provided
        if content_type_str:
            try:
                app_label, model = content_type_str.split('.')
                content_type = ContentType.objects.get(app_label=app_label, model=model)
                queryset = queryset.filter(content_type=content_type)
            except (ValueError, ContentType.DoesNotExist):
                return []
        
        # Sort by engagement score (likes + replies + recency)
        return list(queryset.order_by('-total_reactions', '-like_ratio', '-created_at')[:20])
    
    @staticmethod
    def invalidate_comments_cache(content_type_str: str, object_id: int):
        """Invalidate cached comments for a specific object."""
        object_id = str(object_id)
        try:
            app_label, model = content_type_str.split('.')
            content_type = ContentType.objects.get(app_label=app_label, model=model)
            cache.delete(f"comments:{content_type.id}:{object_id}:approved")
        except (ValueError, ContentType.DoesNotExist):
            pass
    
    @staticmethod
    def get_user_comment_activity(user, days: int = 30) -> Dict:
        """
        Get user's comment activity statistics.
        
        Args:
            user: User object
            days: Number of days to analyze
        """
        since_date = timezone.now() - timedelta(days=days)
        
        user_comments = Comment.objects.filter(
            user=user,
            created_at__gte=since_date
        )
        
        stats = user_comments.aggregate(
            total_comments=Count('id'),
            approved_comments=Count('id', filter=Q(status='APPROVED')),
            total_likes_received=Count('reactions', filter=Q(reactions__reaction_type='LIKE')),
            total_dislikes_received=Count('reactions', filter=Q(reactions__reaction_type='DISLIKE'))
        )
        
        # Get user's reactions given
        user_reactions = CommentReaction.objects.filter(
            user=user,
            created_at__gte=since_date
        ).aggregate(
            likes_given=Count('id', filter=Q(reaction_type='LIKE')),
            dislikes_given=Count('id', filter=Q(reaction_type='DISLIKE'))
        )
        
        return {**stats, **user_reactions}


class ProjectCommentService:
    """
    Service class specifically for project comments.
    Handles project-specific comment operations and integrations.
    """
    
    @staticmethod
    def get_project_comments(project_id: int, user=None) -> List[Comment]:
        """Get comments for a specific project."""
        return CommentService.get_comments_for_object(
            'project.project', 
            project_id, 
            user,
            include_pending=user and hasattr(user, 'role') and user.role == 0
        )
    
    @staticmethod
    def add_project_comment(user, project_id: int, content: str, 
                          parent_id: Optional[int] = None) -> Comment:
        """Add comment to a project."""
        # Validate project exists and is active
        # try:
        #     project = Project.objects.get(id=project_id, visible=True)
        # except Project.DoesNotExist:
        #     raise ValueError("پروژه یافت نشد یا غیرفعال است")
        
        comment, created = CommentService.create_comment(
            user, 'project.project', project_id, content, parent_id
        )
        
        return comment
        # comment, created = CommentService.create_comment(
        #     user, 'project.project', project_id, content, parent_id
        # )
        
        # return comment
    
    @staticmethod
    def get_project_comment_summary(project_id: int) -> Dict:
        """Get comment summary for a project."""
        stats = CommentService.get_comment_statistics('project.project', project_id)
        
        # Add project-specific metrics
        try:
            project = Project.objects.get(id=project_id)
            stats['project_title'] = project.title
            stats['project_visible'] = project.visible
            
            # Calculate engagement rate (comments per view - if tracking views)
            # This would require view tracking implementation
            
        except Project.DoesNotExist:
            pass
        
        return stats


class CommentNotificationService:
    """
    Service for handling comment-related notifications.
    Can be extended to integrate with notification systems.
    """
    
    @staticmethod
    def notify_comment_created(comment: Comment):
        """
        Handle notifications when a new comment is created.
        This is a placeholder for future notification integration.
        """
        # Future implementation could:
        # - Send email to project owner
        # - Create in-app notification
        # - Send push notification
        # - Log to analytics
        pass
    
    @staticmethod
    def notify_comment_approved(comment: Comment):
        """Handle notifications when a comment is approved."""
        # Future implementation could:
        # - Notify comment author
        # - Update project metrics
        pass
    
    @staticmethod
    def notify_comment_reply(comment: Comment):
        """Handle notifications when someone replies to a comment."""
        if comment.parent:
            # Future implementation could:
            # - Notify parent comment author
            # - Send email notification
            pass


class CommentExportService:
    """
    Service for exporting comment data in various formats.
    """
    
    @staticmethod
    def export_to_csv(queryset, include_content: bool = True) -> str:
        """
        Export comments to CSV format.
        
        Args:
            queryset: Comment queryset to export
            include_content: Whether to include full comment content
        """
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        headers = [
            'ID', 'کاربر', 'وضعیت', 'نوع محتوا', 'شناسه آبجکت',
            'تعداد لایک', 'تعداد دیسلایک', 'تاریخ ایجاد'
        ]
        
        if include_content:
            headers.insert(2, 'محتوا')
        
        writer.writerow(headers)
        
        # Write data
        for comment in queryset.select_related('user', 'content_type'):
            row = [
                comment.id,
                comment.user.full_name if hasattr(comment.user, 'full_name') else comment.user.username,
                comment.get_status_display(),
                comment.content_type.model,
                comment.object_id,
                comment.likes_count,
                comment.dislikes_count,
                comment.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            if include_content:
                row.insert(2, comment.content[:100])  # Truncate long content
            
            writer.writerow(row)
        
        return output.getvalue()
    
    @staticmethod
    def export_project_comments(project_id: int, format: str = 'csv') -> str:
        """Export all comments for a specific project."""
        comments = Comment.objects.filter(
            content_type__app_label='project',
            content_type__model='project',
            object_id=project_id
        ).order_by('-created_at')
        
        if format.lower() == 'csv':
            return CommentExportService.export_to_csv(comments)
        else:
            raise ValueError("فرمت پشتیبانی نشده")


# Utility functions for common operations
def get_or_create_content_type(app_label: str, model: str) -> ContentType:
    """Helper to get content type safely."""
    try:
        return ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:
        raise ValueError(f"Content type {app_label}.{model} not found")


def can_user_moderate_comments(user) -> bool:
    """Check if user has comment moderation permissions."""
    return user and hasattr(user, 'role') and user.role == 0


def format_comment_content(content: str, max_length: int = 100) -> str:
    """Format comment content for display."""
    if len(content) <= max_length:
        return content
    return content[:max_length-3] + "..."