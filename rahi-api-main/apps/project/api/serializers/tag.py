from rest_framework import serializers
from django.db.models import Count, Q
from apps.project import models


class TagSerializer(serializers.ModelSerializer):
    """
    Basic tag serializer for CRUD operations.
    Used for listing, creating, updating tags.
    """
    project_count = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = models.Tag
        exclude = ["deleted", "deleted_at", "created_at", "updated_at"]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_project_count(self, obj):
        """Return number of projects using this tag"""
        return obj.projects.filter(visible=True).count()
    
    def validate_name(self, value):
        """Clean and validate tag name"""
        if not value:
            raise serializers.ValidationError("نام تگ الزامی است")
        
        # Clean the name
        value = value.strip().lower()
        
        if len(value) < 2:
            raise serializers.ValidationError("نام تگ باید حداقل 2 کاراکتر باشد")
        
        if len(value) > 100:
            raise serializers.ValidationError("نام تگ نمی‌تواند بیش از 100 کاراکتر باشد")
        
        # Check for invalid characters (optional - customize as needed)
        if not value.replace('-', '').replace('_', '').replace(' ', '').isalnum():
            raise serializers.ValidationError("نام تگ فقط می‌تواند شامل حروف، اعداد، خط تیره و زیرخط باشد")
            
        queryset = models.Tag.objects.filter(name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError("تگی با این نام قبلاً ثبت شده است")
        
        return value


class TagCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new tags.
    Simplified version for creation form.
    """
    class Meta:
        model = models.Tag
        fields = ["name", "description"]
    
    def validate_name(self, value):
        """Same validation as TagSerializer"""
        return TagSerializer().validate_name(value)


class ProjectTagSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for tags when displayed within project context.
    Used in project detail views and related project suggestions.
    """
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = models.Tag
        fields = ["id", "name", "category", "category_display", "description"]


class RelatedProjectSerializer(serializers.ModelSerializer):
    """
    Serializer for projects suggested based on shared tags.
    Includes additional fields showing relationship strength.
    """
    shared_tags_count = serializers.IntegerField(read_only=True)
    common_tags = ProjectTagSerializer(many=True, read_only=True, source='tags')
    
    class Meta:
        model = models.Project
        fields = [
            "id", "title", "description", "company", "leader",
            "shared_tags_count", "common_tags"
        ]
    
    def to_representation(self, instance):
        """Add media URLs to representation"""
        rep = super().to_representation(instance)
        rep["image"] = instance.image.url if instance.image else None
        
        # Filter common tags to only show shared ones if context provides original project
        original_project_tags = self.context.get('original_project_tags')
        if original_project_tags:
            shared_tags = instance.tags.filter(id__in=original_project_tags)
            rep['common_tags'] = ProjectTagSerializer(shared_tags, many=True).data
        
        return rep


class ProjectTagUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating project tags.
    Handles adding/removing tags from projects.
    """
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="فهرست IDهای تگ‌هایی که می‌خواهید به پروژه اضافه کنید"
    )
    tags = ProjectTagSerializer(many=True, read_only=True)
    
    class Meta:
        model = models.Project
        fields = ["id", "title", "tags", "tag_ids"]
        read_only_fields = ["id", "title", "tags"]
    
    def validate_tag_ids(self, value):
        """Validate that all provided tag IDs exist"""
        if not value:
            return value
        
        # Remove duplicates while preserving order
        value = list(dict.fromkeys(value))
        
        # Check if all tags exist
        existing_tags = models.Tag.objects.filter(id__in=value)
        existing_ids = set(str(tag.id) for tag in existing_tags)
        provided_ids = set(str(id) for id in value)
        
        if len(existing_ids) != len(provided_ids):
            invalid_ids = provided_ids - existing_ids
            raise serializers.ValidationError(
                f"تگ‌های زیر یافت نشدند: {', '.join(invalid_ids)}"
            )
        
        return value
    
    def update(self, instance, validated_data):
        """Update project tags"""
        tag_ids = validated_data.pop('tag_ids', None)
        
        if tag_ids is not None:
            if tag_ids:
                # Set new tags
                tags = models.Tag.objects.filter(id__in=tag_ids)
                instance.tags.set(tags)
            else:
                # Clear all tags
                instance.tags.clear()
        
        return super().update(instance, validated_data)


class TagAnalyticsSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for tag analytics.
    Shows tag usage statistics and related information.
    """
    project_count = serializers.IntegerField(read_only=True)
    visible_project_count = serializers.IntegerField(read_only=True)
    recent_projects = serializers.SerializerMethodField()
    
    class Meta:
        model = models.Tag
        exclude = ["deleted", "deleted_at"]
    
    def get_recent_projects(self, obj):
        """Get recent projects using this tag"""
        recent = obj.projects.filter(visible=True).order_by('-created_at')[:5]
        return [{"id": str(p.id), "title": p.title, "company": p.company} for p in recent]