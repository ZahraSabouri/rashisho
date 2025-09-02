from typing import Dict, List, Optional, Union
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import Model, Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.comments.models import Comment, CommentReaction


class CommentCacheManager:
    """
    Centralized cache management for comments.
    Handles cache keys, invalidation, and TTL settings.
    """
    
    # Cache key templates
    COMMENTS_KEY = "comments:{content_type_id}:{object_id}:status:{status}"
    COMMENT_COUNT_KEY = "comment_count:{content_type_id}:{object_id}:status:{status}"
    USER_REACTIONS_KEY = "user_reactions:{user_id}:{comment_id}"
    TRENDING_COMMENTS_KEY = "trending_comments:{content_type_id}:{days}"
    COMMENT_STATS_KEY = "comment_stats:{content_type_id}:{object_id}"
    
    # Cache timeouts (in seconds)
    COMMENTS_TTL = 300  # 5 minutes
    COUNT_TTL = 600     # 10 minutes
    REACTIONS_TTL = 3600  # 1 hour
    TRENDING_TTL = 1800   # 30 minutes
    STATS_TTL = 900     # 15 minutes
    
    @classmethod
    def get_comments_cache_key(cls, content_type_id: int, object_id: int, status: str = 'approved'):
        """Generate cache key for comments list."""
        return cls.COMMENTS_KEY.format(
            content_type_id=content_type_id,
            object_id=object_id,
            status=status
        )
    
    @classmethod
    def get_comment_count_cache_key(cls, content_type_id: int, object_id: int, status: str = 'approved'):
        """Generate cache key for comment count."""
        return cls.COMMENT_COUNT_KEY.format(
            content_type_id=content_type_id,
            object_id=object_id,
            status=status
        )
    
    @classmethod
    def get_user_reactions_cache_key(cls, user_id: int, comment_id: int):
        """Generate cache key for user reactions."""
        return cls.USER_REACTIONS_KEY.format(user_id=user_id, comment_id=comment_id)
    
    @classmethod
    def invalidate_object_cache(cls, content_type_id: int, object_id: int):
        """Invalidate all cache entries for a specific object."""
        patterns = [
            cls.get_comments_cache_key(content_type_id, object_id, 'approved'),
            cls.get_comments_cache_key(content_type_id, object_id, 'all'),
            cls.get_comment_count_cache_key(content_type_id, object_id, 'approved'),
            cls.get_comment_count_cache_key(content_type_id, object_id, 'all'),
            cls.COMMENT_STATS_KEY.format(content_type_id=content_type_id, object_id=object_id)
        ]
        
        cache.delete_many(patterns)
    
    @classmethod
    def invalidate_user_reactions_cache(cls, user_id: int, comment_ids: List[int]):
        """Invalidate user reactions cache for multiple comments."""
        keys = [cls.get_user_reactions_cache_key(user_id, cid) for cid in comment_ids]
        cache.delete_many(keys)


class CommentPermissionChecker:
    """
    Utility class for checking comment-related permissions.
    Centralizes permission logic for consistency.
    """
    
    @staticmethod
    def can_create_comment(user, target_object: Model) -> bool:
        """Check if user can create comments on the target object."""
        if not user or not user.is_authenticated:
            return False
        
        # Check if target object supports comments (could be model-specific)
        if hasattr(target_object, 'allow_comments'):
            return target_object.allow_comments
        
        # For projects, check if visible
        if hasattr(target_object, 'visible'):
            return target_object.visible
        
        return True
    
    @staticmethod
    def can_edit_comment(user, comment: Comment) -> bool:
        """Check if user can edit a specific comment."""
        if not user or not user.is_authenticated:
            return False
        
        # Admins can always edit
        if hasattr(user, 'role') and user.role == 0:
            return True
        
        # Owner can edit within time limit
        if user == comment.user:
            time_diff = timezone.now() - comment.created_at
            return time_diff.total_seconds() < 900  # 15 minutes
        
        return False
    
    @staticmethod
    def can_delete_comment(user, comment: Comment) -> bool:
        """Check if user can delete a specific comment."""
        if not user or not user.is_authenticated:
            return False
        
        # Only admins can delete comments
        return hasattr(user, 'role') and user.role == 0
    
    @staticmethod
    def can_moderate_comments(user) -> bool:
        """Check if user can moderate comments (approve/reject)."""
        if not user or not user.is_authenticated:
            return False
        
        return hasattr(user, 'role') and user.role == 0
    
    @staticmethod
    def can_view_pending_comments(user) -> bool:
        """Check if user can view pending comments."""
        return CommentPermissionChecker.can_moderate_comments(user)


class CommentQueryHelper:
    """
    Helper class for building optimized comment queries.
    Provides common query patterns with proper joins and filters.
    """
    
    @staticmethod
    def get_base_queryset():
        """Get base comment queryset with optimal joins."""
        return Comment.objects.select_related(
            'user', 'content_type', 'parent', 'approved_by'
        ).prefetch_related('reactions')
    
    @staticmethod
    def get_approved_comments_for_object(content_type: ContentType, object_id: int):
        """Get approved comments for a specific object."""
        return CommentQueryHelper.get_base_queryset().filter(
            content_type=content_type,
            object_id=object_id,
            status='APPROVED',
            parent__isnull=True  # Top-level only
        ).order_by('-created_at')
    
    @staticmethod
    def get_comment_with_replies(comment_id: int):
        """Get a comment with its approved replies."""
        from django.db.models import Prefetch
        
        return CommentQueryHelper.get_base_queryset().filter(
            id=comment_id
        ).prefetch_related(
            Prefetch(
                'replies',
                queryset=Comment.objects.filter(status='APPROVED').select_related('user'),
                to_attr='approved_replies'
            )
        ).first()
    
    @staticmethod
    def get_user_comments(user, status: Optional[str] = None):
        """Get comments by a specific user."""
        queryset = CommentQueryHelper.get_base_queryset().filter(user=user)
        
        if status:
            queryset = queryset.filter(status=status.upper())
        
        return queryset.order_by('-created_at')
    
    @staticmethod
    def get_pending_comments_for_moderation():
        """Get pending comments for moderation."""
        return CommentQueryHelper.get_base_queryset().filter(
            status='PENDING'
        ).order_by('created_at')  # Oldest first for FIFO processing


class CommentValidator:
    """
    Validation utilities for comment data.
    Centralizes validation logic for consistency.
    """
    
    MIN_CONTENT_LENGTH = 5
    MAX_CONTENT_LENGTH = 2000
    
    @classmethod
    def validate_content(cls, content: str) -> str:
        """Validate and clean comment content."""
        if not content or not isinstance(content, str):
            raise ValueError("محتوای نظر الزامی است")
        
        content = content.strip()
        
        if len(content) < cls.MIN_CONTENT_LENGTH:
            raise ValueError(f"نظر باید حداقل {cls.MIN_CONTENT_LENGTH} کاراکتر داشته باشد")
        
        if len(content) > cls.MAX_CONTENT_LENGTH:
            raise ValueError(f"نظر نمی‌تواند بیشتر از {cls.MAX_CONTENT_LENGTH} کاراکتر باشد")
        
        return content
    
    @staticmethod
    def validate_reaction_type(reaction_type: str) -> str:
        """Validate reaction type."""
        if reaction_type not in ['LIKE', 'DISLIKE']:
            raise ValueError("نوع واکنش باید LIKE یا DISLIKE باشد")
        
        return reaction_type.upper()
    
    @staticmethod
    def validate_content_type_string(content_type_str: str) -> ContentType:
        """Validate and parse content type string."""
        if not content_type_str or '.' not in content_type_str:
            raise ValueError("فرمت نوع محتوا نامعتبر است")
        
        try:
            app_label, model = content_type_str.split('.')
            return ContentType.objects.get(app_label=app_label, model=model)
        except (ValueError, ContentType.DoesNotExist):
            raise ValueError("نوع محتوای نامعتبر")


class CommentFormatter:
    """
    Formatting utilities for comment display.
    Handles text formatting, truncation, and display logic.
    """
    
    @staticmethod
    def truncate_content(content: str, max_length: int = 100) -> str:
        """Truncate comment content for display."""
        if len(content) <= max_length:
            return content
        return content[:max_length-3] + "..."
    
    @staticmethod
    def format_user_name(user) -> str:
        """Format user name for display."""
        if hasattr(user, 'full_name') and user.full_name:
            return user.full_name
        return user.username or f"کاربر {user.id}"
    
    @staticmethod
    def format_time_ago(created_at) -> str:
        """Format time ago in Persian."""
        now = timezone.now()
        diff = now - created_at
        
        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} ساعت پیش"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} دقیقه پیش"
        else:
            return "همین الان"
    
    @staticmethod
    def format_reaction_count(count: int) -> str:
        """Format reaction count for display."""
        if count >= 1000:
            return f"{count/1000:.1f}k"
        return str(count)


class CommentStatistics:
    """
    Statistical analysis utilities for comments.
    Provides insights and analytics for comment data.
    """
    
    @staticmethod
    def get_engagement_metrics(content_type: ContentType, object_id: int) -> Dict:
        """Get engagement metrics for an object's comments."""
        comments = Comment.objects.filter(
            content_type=content_type,
            object_id=object_id,
            status='APPROVED'
        )
        
        total_comments = comments.count()
        if total_comments == 0:
            return {
                'total_comments': 0,
                'total_reactions': 0,
                'engagement_rate': 0,
                'positive_sentiment': 0
            }
        
        # Calculate metrics
        total_reactions = CommentReaction.objects.filter(
            comment__in=comments
        ).count()
        
        likes = CommentReaction.objects.filter(
            comment__in=comments,
            reaction_type='LIKE'
        ).count()
        
        positive_sentiment = (likes / total_reactions * 100) if total_reactions > 0 else 0
        engagement_rate = (total_reactions / total_comments) if total_comments > 0 else 0
        
        return {
            'total_comments': total_comments,
            'total_reactions': total_reactions,
            'engagement_rate': round(engagement_rate, 2),
            'positive_sentiment': round(positive_sentiment, 2)
        }
    
    @staticmethod
    def get_top_commenters(content_type: ContentType = None, limit: int = 10) -> List[Dict]:
        """Get most active commenters."""
        queryset = Comment.objects.filter(status='APPROVED')
        
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        
        top_commenters = queryset.values(
            'user__id', 'user__username'
        ).annotate(
            comment_count=Count('id'),
            total_likes=Count('reactions', filter=Q(reactions__reaction_type='LIKE'))
        ).order_by('-comment_count')[:limit]
        
        # Add full_name if available
        for commenter in top_commenters:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=commenter['user__id'])
                commenter['full_name'] = getattr(user, 'full_name', user.username)
            except:
                commenter['full_name'] = commenter['user__username']
        
        return list(top_commenters)
    
    @staticmethod
    def get_daily_comment_stats(days: int = 30) -> List[Dict]:
        """Get daily comment statistics."""
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        daily_stats = Comment.objects.filter(
            created_at__date__range=[start_date, end_date]
        ).extra(
            select={'date': 'date(created_at)'}
        ).values('date').annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='APPROVED')),
            pending=Count('id', filter=Q(status='PENDING'))
        ).order_by('date')
        
        return list(daily_stats)


# Convenience functions for common operations
def get_comment_count(content_type_str: str, object_id: int, status: str = 'APPROVED') -> int:
    """Get comment count for an object."""
    try:
        app_label, model = content_type_str.split('.')
        content_type = ContentType.objects.get(app_label=app_label, model=model)
        
        # Check cache first
        cache_key = CommentCacheManager.get_comment_count_cache_key(
            content_type.id, object_id, status.lower()
        )
        
        count = cache.get(cache_key)
        if count is not None:
            return count
        
        # Calculate count
        count = Comment.objects.filter(
            content_type=content_type,
            object_id=object_id,
            status=status
        ).count()
        
        # Cache the result
        cache.set(cache_key, count, CommentCacheManager.COUNT_TTL)
        return count
        
    except (ValueError, ContentType.DoesNotExist):
        return 0


def get_user_reaction_to_comment(user_id: int, comment_id: int) -> Optional[str]:
    """Get user's reaction to a specific comment."""
    cache_key = CommentCacheManager.get_user_reactions_cache_key(user_id, comment_id)
    
    reaction = cache.get(cache_key)
    if reaction is not None:
        return reaction if reaction != 'NONE' else None
    
    try:
        reaction_obj = CommentReaction.objects.get(
            user_id=user_id, 
            comment_id=comment_id
        )
        reaction_type = reaction_obj.reaction_type
    except CommentReaction.DoesNotExist:
        reaction_type = 'NONE'
    
    cache.set(cache_key, reaction_type, CommentCacheManager.REACTIONS_TTL)
    return reaction_type if reaction_type != 'NONE' else None


def is_comment_editable(user, comment: Comment) -> bool:
    """Check if a comment is editable by the user."""
    return CommentPermissionChecker.can_edit_comment(user, comment)


def format_comment_for_display(comment: Comment, user=None) -> Dict:
    """Format comment data for frontend display."""
    return {
        'id': comment.id,
        'content': comment.content,
        'user': {
            'id': comment.user.id,
            'name': CommentFormatter.format_user_name(comment.user),
            'username': comment.user.username
        },
        'created_at': comment.created_at.isoformat(),
        'time_ago': CommentFormatter.format_time_ago(comment.created_at),
        'likes_count': comment.likes_count,
        'dislikes_count': comment.dislikes_count,
        'replies_count': comment.replies_count,
        'user_reaction': get_user_reaction_to_comment(user.id, comment.id) if user and user.is_authenticated else None,
        'is_editable': is_comment_editable(user, comment) if user else False,
        'status': comment.status
    }