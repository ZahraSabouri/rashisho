from rest_framework import serializers
from apps.blog.models import Post, PostImage
from apps.project.models import Project

class PostImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ["id", "image", "created_at", "updated_at"]

    def validate(self, attrs):
        post = self.context.get("post")
        if post and post.images.count() >= 10:
            raise serializers.ValidationError({"image": "حداکثر ۱۰ تصویر مجاز است."})
        return attrs


class PostSerializer(serializers.ModelSerializer):
    images = PostImageSerializer(many=True, read_only=True)
    related_projects = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Project.objects.all(), required=False
    )

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "image",
            "video",
            "content",
            "related_projects",
            "images",
            "created_at",
            "updated_at",
        ]

    def validate_related_projects(self, value):
        if len(value) > 3:
            raise serializers.ValidationError("حداکثر ۳ پروژه مرتبط مجاز است.")
        return value

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["image"] = instance.image.url if instance.image else None
        rep["video"] = instance.video.url if instance.video else None
        # lightweight project chip display (id/title) for FE
        rep["related_projects"] = [{"id": str(p.id), "title": p.title} for p in instance.related_projects.all()]
        return rep
