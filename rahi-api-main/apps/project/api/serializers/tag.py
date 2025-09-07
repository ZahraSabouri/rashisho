from rest_framework import serializers
from django.db.models import Count, Q
from apps.project import models


class TagSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = models.Tag
        fields = ["name", "description", "category"] 
    
    def validate_name(self, value):
        return TagSerializer().validate_name(value)


class ProjectTagSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = models.Tag
        fields = ["id", "name", "category", "category_display", "description"]


class RelatedProjectSerializer(serializers.ModelSerializer):
    shared_tags_count = serializers.IntegerField(read_only=True)
    common_tags = ProjectTagSerializer(many=True, read_only=True, source='tags')
    
    class Meta:
        model = models.Project
        fields = [
            "id", "title", "description", "company", "leader",
            "shared_tags_count", "common_tags"
        ]
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["image"] = instance.image.url if instance.image else None
        
        # Filter common tags to only show shared ones if context provides original project
        original_project_tags = self.context.get('original_project_tags')
        if original_project_tags:
            shared_tags = instance.tags.filter(id__in=original_project_tags)
            rep['common_tags'] = ProjectTagSerializer(shared_tags, many=True).data
        
        return rep


class InlineTagCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    category = serializers.ChoiceField(choices=models.Tag.TagCategory.choices, required=False)
    description = serializers.CharField(allow_blank=True, required=False)

    def validate_name(self, value):
        return TagSerializer().validate_name(value)


class ProjectTagUpdateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="فهرست IDهای تگ‌هایی که می‌خواهید به پروژه اضافه کنید"
    )
    new_tags = InlineTagCreateSerializer(many=True, required=False, write_only=True)

    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = models.Project
        fields = ["id", "title", "tags", "tag_ids", "new_tags"]
        read_only_fields = ["id", "title", "tags"]
    
    def validate_tag_ids(self, value):
        if not value:
            return value
        value = list(dict.fromkeys(value))
        existing = models.Tag.objects.filter(id__in=value).values_list("id", flat=True)
        missing = set(map(str, value)) - set(map(str, existing))
        if missing:
            raise serializers.ValidationError(f"Unknown tag ids: {', '.join(missing)}")
        return value

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop("tag_ids", None)
        new_tags_payload = validated_data.pop("new_tags", [])

        created_or_existing_ids = []
        for item in new_tags_payload:
            name = item["name"].strip().lower()
            defaults = {
                "category": item.get("category") or models.Tag.TagCategory.KEYWORD,
                "description": item.get("description", ""),
            }
            tag_obj, _ = models.Tag.objects.update_or_create(name=name, defaults=defaults)
            created_or_existing_ids.append(tag_obj.id)

        if tag_ids is not None or created_or_existing_ids:
            ids_to_set = set(tag_ids or [])
            ids_to_set.update(created_or_existing_ids)
            if ids_to_set:
                instance.tags.set(models.Tag.objects.filter(id__in=ids_to_set))
            else:
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