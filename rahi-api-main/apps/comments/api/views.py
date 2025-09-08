import csv
from datetime import datetime
from io import StringIO

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework import mixins
from django_filters.rest_framework import DjangoFilterBackend

from apps.api.permissions import IsAdminOrReadOnlyPermission, IsSysgod, IsUser
from apps.api.pagination import Pagination
# from apps.api.pagination import StandardResultsSetPagination
from apps.comments.models import Comment, CommentReaction, CommentModerationLog
from apps.comments.api.serializers import (
    CommentSerializer, CommentListSerializer, CommentReactionSerializer,
    CommentModerationSerializer, BulkCommentActionSerializer,
    CommentExportSerializer
)

from apps.api.schema import TaggedAutoSchema

class CommentViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Comments"])
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    # pagination_class = StandardResultsSetPagination
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'content_type', 'object_id', 'parent']
    search_fields = ['content', 'user__username', 'user__first_name', 'user__last_name']
    ordering_fields = ['created_at', 'updated_at', 'likes_count', 'dislikes_count']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Get comments based on user role and filters.
        Regular users see only approved comments, admins see all.
        """
        user = self.request.user
        
        # Base queryset with optimized queries
        queryset = Comment.objects.select_related(
            'user', 'content_type', 'parent', 'approved_by'
        ).prefetch_related(
            Prefetch(
                'replies',
                queryset=Comment.objects.filter(status='APPROVED').select_related('user')
            ),
            'reactions'
        )
        
        # Filter based on user role
        if hasattr(user, 'role') and user.role == 0:  # Admin
            # Admins can see all comments
            pass
        else:
            # Regular users see only approved comments
            queryset = queryset.filter(status='APPROVED')
        
        # Filter by content type and object if provided
        content_type = self.request.query_params.get('content_type')
        object_id = self.request.query_params.get('object_id')
        
        if content_type and object_id:
            try:
                app_label, model = content_type.split('.')
                ct = ContentType.objects.get(app_label=app_label, model=model)
                queryset = queryset.filter(content_type=ct, object_id=object_id)
            except (ValueError, ContentType.DoesNotExist):
                return Comment.objects.none()
        
        # Filter top-level comments only if not filtering by parent
        if not self.request.query_params.get('parent'):
            queryset = queryset.filter(parent__isnull=True)
        
        return queryset

    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return CommentListSerializer
        return CommentSerializer

    def perform_create(self, serializer):
        """Create comment with proper user assignment"""
        # serializer.save(user=self.request.user)
        serializer.save() 

    def update(self, request, *args, **kwargs):
        """Only allow content updates by owner or admin"""
        comment = self.get_object()
        
        # Check permission
        if request.user != comment.user and not (hasattr(request.user, 'role') and request.user.role == 0):
            raise PermissionDenied("شما مجاز به ویرایش این نظر نیستید")
        
        # Check edit time limit for regular users
        if request.user == comment.user:
            time_diff = timezone.now() - comment.created_at
            if time_diff.total_seconds() > 900:  # 15 minutes
                raise PermissionDenied("زمان ویرایش نظر گذشته است")
        
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Only admins can delete comments"""
        if not (hasattr(request.user, 'role') and request.user.role == 0):
            raise PermissionDenied("شما مجاز به حذف نظرات نیستید")
        
        comment = self.get_object()
        
        # Log the deletion
        CommentModerationLog.objects.create(
            comment=comment,
            moderator=request.user,
            action='DELETED',
            reason=request.data.get('reason', '')
        )
        
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        """Add or update user reaction to comment"""
        comment = self.get_object()
        reaction_type = request.data.get('reaction_type')
        
        if reaction_type not in ['LIKE', 'DISLIKE']:
            return Response(
                {'error': 'نوع واکنش باید LIKE یا DISLIKE باشد'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create reaction
        reaction, created = CommentReaction.objects.get_or_create(
            comment=comment,
            user=request.user,
            defaults={'reaction_type': reaction_type}
        )
        
        if not created and reaction.reaction_type != reaction_type:
            # Update existing reaction
            reaction.reaction_type = reaction_type
            reaction.save()
            message = 'واکنش به‌روزرسانی شد'
        elif not created and reaction.reaction_type == reaction_type:
            # Remove reaction if same type clicked
            reaction.delete()
            message = 'واکنش حذف شد'
            return Response({'message': message}, status=status.HTTP_200_OK)
        else:
            message = 'واکنش اضافه شد'
        
        # Return updated comment data
        serializer = self.get_serializer(comment)
        return Response({
            'message': message,
            'comment': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'])
    def remove_reaction(self, request, pk=None):
        """Remove user reaction from comment"""
        comment = self.get_object()
        
        try:
            reaction = CommentReaction.objects.get(comment=comment, user=request.user)
            reaction.delete()
            
            serializer = self.get_serializer(comment)
            return Response({
                'message': 'واکنش حذف شد',
                'comment': serializer.data
            }, status=status.HTTP_200_OK)
        except CommentReaction.DoesNotExist:
            return Response(
                {'error': 'واکنشی یافت نشد'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'], permission_classes=[IsSysgod])
    def approve(self, request, pk=None):
        comment = self.get_object()
        old_status = comment.status
        reason = request.data.get('reason', '')

        if comment.status == 'APPROVED':
            return Response(
                {'error': 'این نظر قبلاً تایید شده است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        comment.approve(request.user)

        CommentModerationLog.objects.create(
            comment=comment,
            moderator=request.user,
            action='APPROVED',
            reason=reason,
            previous_status=old_status,
            new_status=comment.status,
        )

        return Response({'detail': 'نظر تایید شد.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsSysgod])
    def reject(self, request, pk=None):
        comment = self.get_object()
        old_status = comment.status
        reason = request.data.get('reason', '')
        
        if comment.status == 'REJECTED':
            return Response(
                {'error': 'این نظر قبلاً رد شده است'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment.reject(request.user)
        
        # Log the action
        CommentModerationLog.objects.create(
            comment=comment,
            moderator=request.user,
            action='REJECTED',
            reason=reason,
            previous_status=old_status,
            new_status=comment.status,
        )
        
        serializer = self.get_serializer(comment)
        return Response({
            'message': 'نظر رد شد',
            'comment': serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
            comment = self.get_object()
            self.check_object_permissions(request, comment)
            old_status = comment.status
            reason = request.data.get('reason', '')

            CommentModerationLog.objects.create(
                comment=comment,
                moderator=request.user if request.user.is_authenticated else None,
                action='DELETED',
                reason=reason,
                previous_status=old_status,
                new_status=old_status,
            )
            return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['post'], permission_classes=[IsSysgod])
    def bulk_action(self, request):
        ser = BulkCommentActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        action_type = ser.validated_data['action']          # 'approve' | 'reject' | 'delete'
        reason = ser.validated_data.get('reason', '')
        ids = ser.validated_data['comment_ids']

        comments = Comment.objects.filter(id__in=ids)
        with transaction.atomic():
            for c in comments.select_for_update():
                old = c.status
                if action_type == 'approve':
                    c.approve(request.user)
                    new = c.status
                    log_action = 'APPROVED'
                elif action_type == 'reject':
                    c.reject(request.user, reason=reason)
                    new = c.status
                    log_action = 'REJECTED'
                else:  # delete
                    new = old
                    log_action = 'DELETED'

                CommentModerationLog.objects.create(
                    comment=c,
                    moderator=request.user,
                    action=log_action,
                    reason=reason,
                    previous_status=old,
                    new_status=new,
                )

            if action_type == 'delete':
                comments.delete()

        return Response({'detail': 'عملیات با موفقیت انجام شد.'})

    @action(detail=False, methods=['get'], permission_classes=[IsSysgod])
    def export(self, request):
        """Export comments to CSV (admin only)"""
        # Get filters from request
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        status_filter = request.query_params.get('status')
        
        queryset = Comment.objects.select_related(
            'user', 'content_type', 'parent', 'approved_by'
        ).order_by('-created_at')
        
        # Apply filters
        if content_type and object_id:
            try:
                app_label, model = content_type.split('.')
                ct = ContentType.objects.get(app_label=app_label, model=model)
                queryset = queryset.filter(content_type=ct, object_id=object_id)
            except (ValueError, ContentType.DoesNotExist):
                pass
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'محتوا', 'وضعیت', 'نام کاربر', 'نام کاربری',
            'نوع محتوا', 'شناسه آبجکت', 'پاسخ به', 'تعداد لایک',
            'تعداد دیسلایک', 'تعداد پاسخ', 'تایید شده توسط',
            'تاریخ تایید', 'تاریخ ایجاد', 'تاریخ به‌روزرسانی'
        ])
        
        # Write data
        serializer = CommentExportSerializer(queryset, many=True)
        for comment_data in serializer.data:
            writer.writerow([
                comment_data['id'],
                comment_data['content'][:100],  # Truncate long content
                comment_data['status'],
                comment_data['user_name'] or '',
                comment_data['user_username'] or '',
                comment_data['content_type_name'] or '',
                comment_data['object_id'],
                comment_data['parent_content'][:50] if comment_data['parent_content'] else '',
                comment_data['likes_count'],
                comment_data['dislikes_count'],
                comment_data['replies_count'],
                comment_data['approved_by_name'] or '',
                comment_data['approved_at'] or '',
                comment_data['created_at'],
                comment_data['updated_at']
            ])
        
        # Create response
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        filename = f'comments_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Type'] = 'text/csv; charset=utf-8'
        
        return response

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get comment statistics"""
        # Base queryset
        queryset = Comment.objects.all()
        
        # Filter by content type if provided
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        
        if content_type and object_id:
            try:
                app_label, model = content_type.split('.')
                ct = ContentType.objects.get(app_label=app_label, model=model)
                queryset = queryset.filter(content_type=ct, object_id=object_id)
            except (ValueError, ContentType.DoesNotExist):
                pass
        
        # Calculate statistics
        stats = queryset.aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='APPROVED')),
            pending=Count('id', filter=Q(status='PENDING')),
            rejected=Count('id', filter=Q(status='REJECTED')),
            total_likes=Count('reactions', filter=Q(reactions__reaction_type='LIKE')),
            total_dislikes=Count('reactions', filter=Q(reactions__reaction_type='DISLIKE'))
        )
        
        return Response(stats, status=status.HTTP_200_OK)


class CommentModerationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet
):
    schema = TaggedAutoSchema(tags=["Comments"])
    serializer_class = CommentModerationSerializer
    permission_classes = [IsSysgod]
    queryset = CommentModerationLog.objects.select_related(
        'comment', 'comment__user', 'moderator'
    ).order_by('-created_at')
    # pagination_class = StandardResultsSetPagination
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['action', 'moderator']
    ordering_fields = ['created_at']
    ordering = ['-created_at']