from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
import django_filters.rest_framework as dj_filters 

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.api.pagination import Pagination
from apps.comments.models import Comment, CommentReaction
from apps.comments.api.serializers import (
    CommentSerializer, CommentListSerializer, CommentReactionSerializer

)
from apps.project.api.serializers.comments import ProjectCommentSerializer, ProjectCommentListSerializer
from apps.comments.services import CommentService, ProjectCommentService
from apps.project.models import Project

class ProjectCommentFilterSet(FilterSet):
    """
    FilterSet for /api/v1/project/comments/ that exposes `project_id`
    as an alias for Comment.object_id.
    """
    project_id = dj_filters.CharFilter(field_name="object_id", help_text="Project UUID")
    class Meta:
        model = Comment
        fields = ["status", "parent", "project_id"]


class ProjectCommentViewSet(ModelViewSet):
    """
    ViewSet for managing comments specifically for projects.
    Provides a cleaner API under /api/v1/project/comments/
    """
    # serializer_class = CommentSerializer
    serializer_class = ProjectCommentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProjectCommentFilterSet
    filterset_fields = ['status', 'parent']
    search_fields = ['content']
    ordering_fields = ['created_at', 'likes_count']
    ordering = ['-created_at']

    def get_queryset(self):
        ct = ContentType.objects.get_for_model(Project)
        qs = Comment.objects.filter(content_type=ct)

        project_ct = ContentType.objects.get_for_model(Project)
        qs = Comment.objects.filter(content_type=project_ct)

        if not (hasattr(self.request.user, "role") and self.request.user.role == 0):
            qs = qs.filter(status="APPROVED")
        return qs
    

    def get_serializer_class(self):
        """Choose appropriate serializer based on action"""
        if self.action == 'list':
        #     return CommentListSerializer
        # return CommentSerializer
            return ProjectCommentListSerializer
        return ProjectCommentListSerializer

    def perform_create(self, serializer):
        project_id = serializer.validated_data.get("object_id")
        try:
            Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("پروژه مورد نظر یافت نشد")

        comment = ProjectCommentService.add_project_comment(
            user=self.request.user,
            project_id=project_id,
            content=serializer.validated_data['content'],
            parent_id=serializer.validated_data.get('parent_id'),
        )
        serializer.instance = comment
          
    @action(detail=True, methods=['post'], url_path='react')
    def react(self, request, pk=None):
        """Add or update reaction to a comment"""
        comment = self.get_object()
        serializer = CommentReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        reaction_type = serializer.validated_data['reaction_type']
        
        # Use comment service for reaction logic
        reaction = CommentService.add_or_update_reaction(
            comment=comment,
            user=request.user,
            reaction_type=reaction_type
        )
        
        return Response({
            'message': f'واکنش {reaction_type} ثبت شد',
            'reaction_type': reaction.reaction_type,
            'likes_count': comment.likes_count,
            'dislikes_count': comment.dislikes_count
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path='remove-reaction')
    def remove_reaction(self, request, pk=None):
        """Remove user's reaction from a comment"""
        comment = self.get_object()
        
        try:
            reaction = CommentReaction.objects.get(comment=comment, user=request.user)
            reaction.delete()
            
            # Refresh comment counts
            comment.refresh_from_db()
            
            return Response({
                'message': 'واکنش حذف شد',
                'likes_count': comment.likes_count,
                'dislikes_count': comment.dislikes_count
            }, status=status.HTTP_200_OK)
        except CommentReaction.DoesNotExist:
            raise ValidationError("واکنشی برای حذف یافت نشد")

    @action(detail=True, methods=['post'], url_path='approve', 
            permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """Approve comment (admin only)"""
        if not self._can_moderate():
            raise ValidationError("شما مجوز تایید نظرات را ندارید")
            
        comment = self.get_object()
        CommentService.approve_comment(comment, request.user)
        
        return Response({
            'message': 'نظر تایید شد',
            'status': comment.status
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject',
            permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """Reject comment (admin only)"""
        if not self._can_moderate():
            raise ValidationError("شما مجوز رد نظرات را ندارید")
            
        comment = self.get_object()
        reason = request.data.get('reason', 'بدون دلیل مشخص')
        CommentService.reject_comment(comment, request.user, reason)
        
        return Response({
            'message': 'نظر رد شد',
            'status': comment.status
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """Get project comments statistics"""
        project_id = request.query_params.get('project_id')
        
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
                stats = project.get_comment_statistics()
            except Project.DoesNotExist:
                raise ValidationError("پروژه مورد نظر یافت نشد")
        else:
            # Overall project comments stats
            project_content_type = ContentType.objects.get_for_model(Project)
            stats = CommentService.get_overall_statistics(project_content_type)
        
        return Response(stats, status=status.HTTP_200_OK)

    def _can_moderate(self):
        """Check if user can moderate comments"""
        return (self.request.user and 
                hasattr(self.request.user, 'role') and 
                self.request.user.role == 0)


class ProjectCommentByProjectViewSet(ModelViewSet):
    """
    Alternative ViewSet for accessing comments via /api/v1/project/{project_id}/comments/
    This provides a more RESTful nested resource approach.
    """
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    lookup_field = 'project_id'

    def get_queryset(self):
        """Get comments for specific project from URL"""
        project_id = self.kwargs.get('project_id')
        
        if not project_id:
            return Comment.objects.none()
            
        try:
            # Verify project exists
            Project.objects.get(id=project_id)
            
            # Get project comments
            return ProjectCommentService.get_project_comments(
                project_id=project_id,
                user=self.request.user
            )
        except Project.DoesNotExist:
            raise NotFound("پروژه مورد نظر یافت نشد")

    def perform_create(self, serializer):
        """Create comment for specific project"""
        project_id = self.kwargs.get('project_id')
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ValidationError("پروژه مورد نظر یافت نشد")

        # Create comment for this specific project
        comment = ProjectCommentService.add_project_comment(
            user=self.request.user,
            project_id=project_id,
            content=serializer.validated_data['content'],
            parent_id=serializer.validated_data.get('parent_id')
        )
        
        serializer.instance = comment