from rest_framework import serializers
from django.db.models import Count, Q
from slugify import slugify
from apps.project import models



class TagCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TagCategory
        fields = ["id", "code", "title"]


class TagSerializer(serializers.ModelSerializer):
    project_count = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    category_obj = TagCategorySerializer(source="category_ref", read_only=True)

    class Meta:
        model = models.Tag
        exclude = ["deleted", "deleted_at", "created_at", "updated_at"]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_project_count(self, obj):
        return obj.projects.filter(visible=True).count()
    
    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("نام تگ الزامی است")
        
        value = value.strip().lower()
        
        if len(value) < 2:
            raise serializers.ValidationError("نام تگ باید حداقل 2 کاراکتر باشد")
        
        if len(value) > 100:
            raise serializers.ValidationError("نام تگ نمی‌تواند بیش از 100 کاراکتر باشد")
        
        if not value.replace('-', '').replace('_', '').replace(' ', '').isalnum():
            raise serializers.ValidationError("نام تگ فقط می‌تواند شامل حروف، اعداد، خط تیره و زیرخط باشد")
            
        queryset = models.Tag.objects.filter(name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError("تگی با این نام قبلاً ثبت شده است")
        
        return value


class TagCreateSerializer(serializers.ModelSerializer):
    category = serializers.CharField(required=False)        
    category_id = serializers.UUIDField(required=False) 

    class Meta:
        model = models.Tag
        fields = ["name", "description", "category", "category_id"]

    def validate(self, attrs):
        if not attrs.get("category_id") and not attrs.get("category"):
            raise serializers.ValidationError({"category": "category or category_id is required"})
        return attrs
    
    def _resolve_category(self, data):
        from django.utils.text import slugify
        if data.get("category_id"):
            return models.TagCategory.objects.get(id=data["category_id"])
        raw = (data.get("category") or "").strip()
        if not raw:
            raise serializers.ValidationError({"category": "category or category_id is required"})
        cat = (models.TagCategory.objects.filter(code__iexact=raw).first() or
               models.TagCategory.objects.filter(title__iexact=raw).first())
        return cat or models.TagCategory.objects.create(code=slugify(raw), title=raw)

    def validate_name(self, value):
        value = value.strip().lower()
        if len(value) < 2:
            raise serializers.ValidationError("نام تگ باید حداقل ۲ کاراکتر باشد.")
        if models.Tag.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("تگ با این نام وجود دارد.")
        return value

    def create(self, validated_data):
        cat = self._resolve_category(validated_data)
        return models.Tag.objects.create(
            name=validated_data["name"].strip().lower(),
            description=(validated_data.get("description") or ""),
            category_ref=cat,
            category=cat.code,
        )


class ProjectTagSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)

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
    category = serializers.CharField(required=False)
    category_id = serializers.UUIDField(required=False)
    description = serializers.CharField(allow_blank=True, required=False)

    def validate_name(self, value):
        return TagSerializer().validate_name(value)


class ProjectTagUpdateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    new_tags = InlineTagCreateSerializer(many=True, required=False)
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = models.Project
        fields = ["id", "title", "tags", "tag_ids", "new_tags"]
        read_only_fields = ["id", "title", "tags"]

    def _resolve_category(self, item):
        from django.utils.text import slugify
        if item.get("category_id"):
            return models.TagCategory.objects.get(id=item["category_id"])
        raw = (item.get("category") or "KEYWORD").strip()
        cat = models.TagCategory.objects.filter(code__iexact=raw).first() or \
              models.TagCategory.objects.filter(title__iexact=raw).first()
        if cat:
            return cat
        return models.TagCategory.objects.create(code=slugify(raw), title=raw)

    def update(self, instance, validated_data):
        tag_ids = validated_data.get("tag_ids") or []
        new_tags_payload = validated_data.get("new_tags") or []

        created_or_existing_ids = []
        for item in new_tags_payload:
            name = item["name"].strip().lower()
            cat = self._resolve_category(item)
            defaults = {
                "description": item.get("description", "") or "",
                "category": cat.code,
                "category_ref": cat,
            }
            tag_obj, _ = models.Tag.objects.update_or_create(name=name, defaults=defaults)
            created_or_existing_ids.append(tag_obj.id)

        if tag_ids or created_or_existing_ids:
            ids_to_set = set(tag_ids) | set(created_or_existing_ids)
            instance.tags.set(models.Tag.objects.filter(id__in=ids_to_set))
        else:
            instance.tags.clear()

        return instance
    
    def validate_tag_ids(self, value):
        if not value:
            return value
        value = list(dict.fromkeys(value))
        existing = models.Tag.objects.filter(id__in=value).values_list("id", flat=True)
        missing = set(map(str, value)) - set(map(str, existing))
        if missing:
            raise serializers.ValidationError(f"Unknown tag ids: {', '.join(missing)}")
        return value


class TagAnalyticsSerializer(serializers.ModelSerializer):
    project_count = serializers.IntegerField(read_only=True)
    visible_project_count = serializers.IntegerField(read_only=True)
    recent_projects = serializers.SerializerMethodField()
    
    class Meta:
        model = models.Tag
        exclude = ["deleted", "deleted_at"]
    
    def get_recent_projects(self, obj):
        recent = obj.projects.filter(visible=True).order_by('-created_at')[:5]
        return [{"id": str(p.id), "title": p.title, "company": p.company} for p in recent]