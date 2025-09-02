import logging
from django.db.models import Q, Count
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.project import models
from apps.project.api.serializers import project_status as status_serializers
from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.api.pagination import Pagination

logger = logging.getLogger(__name__)


class ProjectStatusViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for project status information.
    Provides read-only access to project activation status.
    """
    serializer_class = status_serializers.ProjectStatusSerializer
    queryset = models.Project.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'visible', 'company']
    search_fields = ['title', 'company', 'description']
    ordering_fields = ['title', 'company', 'created_at', 'is_active']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Use detailed serializer for admin users"""
        if hasattr(self.request.user, 'role') and self.request.user.role == 2:
            return status_serializers.ProjectStatusDetailSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get project status statistics"""
        cache_key = 'project_status_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            total_projects = models.Project.objects.count()
            active_projects = models.Project.objects.filter(is_active=True).count()
            visible_projects = models.Project.objects.filter(visible=True).count()
            selectable_projects = models.Project.objects.filter(
                is_active=True, visible=True
            ).count()
            
            stats = {
                'total_projects': total_projects,
                'active_projects': active_projects,
                'inactive_projects': total_projects - active_projects,
                'visible_projects': visible_projects,
                'hidden_projects': total_projects - visible_projects,
                'selectable_projects': selectable_projects,
                'activation_rate': round(
                    (active_projects / total_projects * 100) if total_projects > 0 else 0, 2
                )
            }
            
            cache.set(cache_key, stats, 300)  # Cache for 5 minutes
        
        return Response(stats)


class ProjectActivationView(APIView):
    """
    View for project activation/deactivation operations.
    Admin-only endpoint for managing project status.
    """
    permission_classes = [IsAdminOrReadOnlyPermission]
    serializer_class = status_serializers.ProjectActivationSerializer

    def post(self, request, *args, **kwargs):
        """Activate or deactivate multiple projects"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = serializer.update_projects_status(serializer.validated_data)
            
            # Clear cache after status update
            cache.delete('project_status_stats')
            cache.delete_many([
                'active_projects_list',
                'homepage_projects',
                'project_list_*'  # Clear project list caches
            ])
            
            return Response({
                'message': f"{result['action']} {result['updated_count']} پروژه با موفقیت انجام شد",
                'details': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Project activation error: {str(e)}")
            return Response({
                'error': 'خطا در به‌روزرسانی وضعیت پروژه‌ها',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SingleProjectStatusView(APIView):
    """
    View for single project status management.
    Allows activation/deactivation of individual projects.
    """
    permission_classes = [IsAdminOrReadOnlyPermission]

    def get(self, request, project_id, *args, **kwargs):
        """Get single project status"""
        project = get_object_or_404(models.Project, id=project_id)
        serializer = status_serializers.ProjectStatusDetailSerializer(project)
        return Response(serializer.data)

    def patch(self, request, project_id, *args, **kwargs):
        """Toggle single project activation status"""
        project = get_object_or_404(models.Project, id=project_id)
        new_status = not project.is_active
        reason = request.data.get('reason', '')
        
        try:
            if new_status:
                project.activate()
                action = 'فعال‌سازی'
            else:
                project.deactivate()
                action = 'غیرفعال‌سازی'
            
            logger.info(
                f"Single project {action}: {project.title} (ID: {project.id}). "
                f"Reason: {reason or 'No reason provided'}"
            )
            
            # Clear relevant caches
            cache.delete('project_status_stats')
            
            serializer = status_serializers.ProjectStatusDetailSerializer(project)
            return Response({
                'message': f"{action} پروژه با موفقیت انجام شد",
                'project': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Single project status update error: {str(e)}")
            return Response({
                'error': 'خطا در تغییر وضعیت پروژه',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)