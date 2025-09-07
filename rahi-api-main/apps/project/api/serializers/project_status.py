from rest_framework import serializers
from apps.project import models


class ProjectStatusSerializer(serializers.ModelSerializer):
    """
    Serializer for project status information.
    Read-only serializer showing current activation state.
    """
    status_display = serializers.CharField(read_only=True)
    can_be_selected = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = models.Project
        fields = ['id', 'title', 'is_active', 'visible', 'status_display', 'can_be_selected']
        read_only_fields = ['id', 'title']


class ProjectActivationSerializer(serializers.Serializer):
    """
    Serializer for project activation/deactivation operations.
    Handles bulk activation and validation.
    """
    project_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="لیست UUID های پروژه‌هایی که می‌خواهید تغییر دهید"
    )
    is_active = serializers.BooleanField(
        help_text="وضعیت جدید: true برای فعال‌سازی، false برای غیرفعال‌سازی"
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="دلیل تغییر وضعیت (اختیاری)"
    )

    def validate_project_ids(self, value):
        """Validate that all project IDs exist"""
        existing_ids = models.Project.objects.filter(
            id__in=value
        ).values_list('id', flat=True)
        
        missing_ids = set(value) - set(existing_ids)
        if missing_ids:
            raise serializers.ValidationError(
                f"پروژه‌های با شناسه‌های زیر یافت نشدند: {', '.join(str(id) for id in missing_ids)}"
            )
        
        return value

    def update_projects_status(self, validated_data):
        """Update project activation status"""
        project_ids = validated_data['project_ids']
        is_active = validated_data['is_active']
        reason = validated_data.get('reason', '')
        
        updated_count = models.Project.objects.filter(
            id__in=project_ids
        ).update(is_active=is_active)
        
        # Log the operation for audit purposes
        import logging
        logger = logging.getLogger(__name__)
        action = "فعال‌سازی" if is_active else "غیرفعال‌سازی"
        logger.info(
            f"Project status update: {action} {updated_count} projects. "
            f"Reason: {reason or 'No reason provided'}"
        )
        
        return {
            'updated_count': updated_count,
            'action': action,
            'reason': reason
        }


class ProjectStatusDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for project status with additional context.
    Used in admin and detailed status views.
    """
    status_display = serializers.CharField(read_only=True)
    can_be_selected = serializers.BooleanField(read_only=True)
    tags_count = serializers.SerializerMethodField()
    allocations_count = serializers.SerializerMethodField()
    
    class Meta:
        model = models.Project
        fields = [
            'id', 'title', 'company', 'is_active', 'visible', 
            'status_display', 'can_be_selected', 'created_at', 
            'updated_at', 'tags_count', 'allocations_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_tags_count(self, obj):
        """Get number of tags for this project"""
        return obj.tags.count()
    
    def get_allocations_count(self, obj):
        """Get number of user allocations for this project"""
        return obj.allocations.count()