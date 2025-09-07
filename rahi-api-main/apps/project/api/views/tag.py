from django.db.models import Count, Q, Prefetch
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status, filters 
from rest_framework.decorators import action 
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.project import models
from apps.project.api.serializers import tag as tag_serializers
from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.api.pagination import Pagination

from apps.api.schema import TaggedAutoSchema

class TagViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Project Tags"])
    
    queryset = models.Tag.objects.all().order_by('name')
    permission_classes = [IsAdminOrReadOnlyPermission]
    pagination_class = Pagination  # FIXED: Use correct pagination class
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    filterset_fields = ['category']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return tag_serializers.TagCreateSerializer
        elif self.action == 'analytics':
            return tag_serializers.TagAnalyticsSerializer
        return tag_serializers.TagSerializer
    
    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by usage - show only used tags if requested
        used_only = self.request.query_params.get('used_only', None)
        if used_only and used_only.lower() == 'true':
            queryset = queryset.filter(projects__isnull=False).distinct()
        
        # Add project count annotation for analytics
        queryset = queryset.annotate(
            project_count=Count('projects', distinct=True),
            visible_project_count=Count('projects', filter=Q(projects__visible=True), distinct=True)
        )
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tag = serializer.save()
        
        cache.delete('popular_tags')
        
        return Response({
            'message': f'تگ "{tag.name}" با موفقیت ایجاد شد',
            'tag': tag_serializers.TagSerializer(tag).data
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update tag and clear related caches"""
        response = super().update(request, *args, **kwargs)
        
        # Clear caches that might be affected
        cache.delete('popular_tags')
        
        return response
    
    def destroy(self, request, *args, **kwargs):
        """Delete tag with validation"""
        tag = self.get_object()
        
        # Check if tag is being used
        project_count = tag.projects.count()
        if project_count > 0:
            return Response({
                'error': f'این تگ در {project_count} پروژه استفاده شده و قابل حذف نیست'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tag_name = tag.name
        response = super().destroy(request, *args, **kwargs)
        
        # Clear caches
        cache.delete('popular_tags')
        
        # Return success message
        return Response({
            'message': f'تگ "{tag_name}" با موفقیت حذف شد'
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['GET'])
    def popular(self, request):
        """
        Get most popular tags based on project usage.
        Results are cached for better performance.
        """
        cache_key = "popular_tags"
        popular_tags = cache.get(cache_key)
        
        if popular_tags is None:
            popular_tags = models.Tag.objects.annotate(
                project_count=Count('projects', filter=Q(projects__visible=True))
            ).filter(
                project_count__gt=0
            ).order_by('-project_count')[:15]
            
            # Cache for 1 hour
            cache.set(cache_key, list(popular_tags), 3600)
        
        serializer = tag_serializers.TagSerializer(popular_tags, many=True)
        return Response({
            'popular_tags': serializer.data,
            'count': len(serializer.data)
        })
    
    @action(detail=True, methods=['GET'])
    def analytics(self, request, pk=None):
        """Get detailed analytics for a specific tag"""
        tag = self.get_object()
        
        # Add annotations for analytics
        tag.project_count = tag.projects.count()
        tag.visible_project_count = tag.projects.filter(visible=True).count()
        
        serializer = self.get_serializer(tag)
        return Response(serializer.data)
    
    @action(detail=False, methods=['GET'])
    def unused(self, request):
        """Get tags that are not used by any project (admin only)"""
        if not request.user.is_staff:
            return Response({'error': 'دسترسی غیر مجاز'}, status=status.HTTP_403_FORBIDDEN)
        
        unused_tags = self.get_queryset().filter(project_count=0)
        page = self.paginate_queryset(unused_tags)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(unused_tags, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='set-category')
    def set_category(self, request, pk=None):
        """
        Minimal “category-only” patch.
        Admin-only (permission class already enforced on the ViewSet).
        """
        tag = self.get_object()
        category = request.data.get('category')
        if category is None:
            return Response({'error': 'category is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Let DRF/model validate the choice
        tag.category = category
        tag.save(update_fields=['category'])

        cache.delete('popular_tags')  # keep caches honest
        return Response({'message': 'category updated', 'tag': tag_serializers.TagSerializer(tag).data})

class ProjectTagManagementView(APIView):
    schema = TaggedAutoSchema(tags=["Project Tags"])
    
    def get_permissions(self):
        """Read operations are public, write operations need admin permission"""
        if self.request.method == 'GET':
            return []
        return [IsAdminOrReadOnlyPermission()]
    
    def get_project(self, project_id):
        """Get project or return 404"""
        return get_object_or_404(models.Project, id=project_id)
    
    def get(self, request, project_id):
        """Get all tags for a specific project"""
        project = self.get_project(project_id)
        
        tags = project.tags.all().order_by('name')
        serializer = tag_serializers.ProjectTagSerializer(tags, many=True)
        
        return Response({
            "project_id": project_id,
            "project_title": project.title,
            "tags": serializer.data,
            "tags_count": tags.count()
        })
    
    def post(self, request, project_id):
        """Add or update tags for a project (admin only)"""
        project = self.get_project(project_id)
        
        serializer = tag_serializers.ProjectTagUpdateSerializer(
            project, 
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            updated_project = serializer.save()
            
            # Clear related projects cache for this project and related ones
            self._clear_related_caches(updated_project)
            
            return Response({
                "message": "تگ‌های پروژه با موفقیت به‌روزرسانی شد",
                "project": {
                    "id": str(updated_project.id),
                    "title": updated_project.title,
                    "tags": tag_serializers.ProjectTagSerializer(
                        updated_project.tags.all(), many=True
                    ).data,
                    "tags_count": updated_project.tags.count()
                }
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def _clear_related_caches(self, project):
        """Clear caches related to this project"""
        cache_keys_to_delete = [
            f"related_projects_{project.id}",
            'popular_tags'
        ]
        
        # Also clear cache for projects that share tags
        project_tags = project.tags.all()
        if project_tags.exists():
            related_projects = models.Project.objects.filter(
                tags__in=project_tags
            ).exclude(id=project.id).distinct()
            
            for related_project in related_projects:
                cache_keys_to_delete.append(f"related_projects_{related_project.id}")
        
        cache.delete_many(cache_keys_to_delete)


class RelatedProjectsView(APIView):
    schema = TaggedAutoSchema(tags=["Project Tags"])
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id):
        """Get related projects based on shared tags"""
        try:
            project = models.Project.objects.get(id=project_id, visible=True)
        except models.Project.DoesNotExist:
            return Response(
                {"error": "پروژه مورد نظر یافت نشد یا قابل نمایش نیست"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check cache first
        cache_key = f"related_projects_{project_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return Response(cached_data)
        
        # Get related projects
        related_projects = self._get_related_projects(project)
        
        # Prepare response data
        serializer = tag_serializers.RelatedProjectSerializer(
            related_projects, 
            many=True,
            context={
                'request': request,
                'original_project_tags': list(project.tags.values_list('id', flat=True))
            }
        )
        
        response_data = {
            "project_id": project_id,
            "project_title": project.title,
            "project_tags": tag_serializers.ProjectTagSerializer(
                project.tags.all(), many=True
            ).data,
            "related_projects": serializer.data,
            "related_count": len(serializer.data)
        }
        
        # Cache for 30 minutes
        cache.set(cache_key, response_data, 1800)
        
        return Response(response_data)
    
    def _get_related_projects(self, project):
        """
        Find related projects using multiple criteria:
        1. Shared tags (primary)
        2. Same study fields (secondary)  
        3. Same company (tertiary)
        """
        project_tags = project.tags.all()
        
        if not project_tags.exists():
            return models.Project.objects.none()
        
        # Get projects with shared tags
        related_projects = models.Project.objects.filter(
            tags__in=project_tags,
            visible=True
        ).exclude(
            id=project.id
        ).prefetch_related(
            'tags', 'study_fields'
        ).annotate(
            shared_tags_count=Count('tags', filter=Q(tags__in=project_tags))
        ).filter(
            shared_tags_count__gt=0
        ).order_by('-shared_tags_count', '-created_at')
        
        # Limit to top 6 most related projects
        return related_projects[:6]