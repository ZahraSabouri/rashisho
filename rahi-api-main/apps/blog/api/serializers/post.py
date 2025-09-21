from rest_framework import serializers
from apps.blog.models import Post, PostImage
from apps.project.models import Project

class PostImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ["id", "image", "created_at", "updated_at"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["image"] = instance.image.url if instance.image else None
        return rep

class PostSerializer(serializers.ModelSerializer):
    images = PostImageSerializer(many=True, read_only=True)
    related_projects = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Project.objects.all(), required=False
    )

    class Meta:
        model = Post
        fields = ["id", "title", "image", "video", "content", "related_projects", "images", "created_at", "updated_at"]

    def validate_related_projects(self, value):
        if len(value) > 3:
            raise serializers.ValidationError("حداکثر ۳ پروژه مرتبط مجاز است.")
        return value

    def _apply_related_projects_from_context(self, post):
        ids = self.context.get("related_project_ids")
        if ids is not None:
            post.related_projects.set(ids)

    def create(self, validated_data):
        # Pop to avoid double-setting (DRF handles when present; context covers multipart case)
        validated_data.pop("related_projects", None)
        post = Post.objects.create(**validated_data)
        self._apply_related_projects_from_context(post)
        return post

    def update(self, instance, validated_data):
        validated_data.pop("related_projects", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        self._apply_related_projects_from_context(instance)
        return instance
