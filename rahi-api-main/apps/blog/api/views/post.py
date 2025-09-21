from django.shortcuts import get_object_or_404
from rest_framework import mixins
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.api.schema import TaggedAutoSchema
from apps.blog.models import Post, PostImage
from apps.blog.api.serializers.post import PostSerializer, PostImageSerializer
import json

class PostViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Blog"])
    queryset = Post.objects.all().order_by("-created_at")
    serializer_class = PostSerializer
    permission_classes = [IsAdminOrReadOnlyPermission]
    parser_classes = (MultiPartParser, FormParser)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        data = self.request.data

        ids = []
        if hasattr(data, "getlist"):  # multipart/form-data
            ids = data.getlist("related_projects[]") or data.getlist("related_projects") or []
            if not ids and data.get("related_projects"):
                try:
                    parsed = json.loads(data.get("related_projects"))
                    if isinstance(parsed, (list, tuple)):
                        ids = list(parsed)
                except (TypeError, ValueError):
                    pass
        else:  # application/json
            ids = data.get("related_projects") or data.get("related_projects[]") or []
        if isinstance(ids, str):  # handle comma-separated
            ids = [x.strip() for x in ids.split(",") if x.strip()]
        ctx["related_project_ids"] = ids

        images = []
        if hasattr(self.request.FILES, "getlist"):
            images = (
                self.request.FILES.getlist("images[]")
                or self.request.FILES.getlist("images")
                or []
            )
        ctx["extra_images"] = images
        return ctx

    def perform_create(self, serializer):
        post = serializer.save()  # sets basic fields

        ids = self.get_serializer_context().get("related_project_ids") or []
        if ids:
            post.related_projects.set(ids)

        files = self.get_serializer_context().get("extra_images") or []
        if files:
            if post.images.count() + len(files) > 10:
                raise ValidationError({"images": "حداکثر ۱۰ تصویر مجاز است."})
            for f in files:
                PostImage.objects.create(post=post, image=f)

    def perform_update(self, serializer):
        post = serializer.save()

        files = self.get_serializer_context().get("extra_images") or []
        if files:
            if post.images.count() + len(files) > 10:
                raise ValidationError({"images": "حداکثر ۱۰ تصویر مجاز است."})
            for f in files:
                PostImage.objects.create(post=post, image=f)

class PostImageViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, GenericViewSet):
    schema = TaggedAutoSchema(tags=["Blog"])
    serializer_class = PostImageSerializer
    permission_classes = [IsAdminOrReadOnlyPermission]

    def get_queryset(self):
        return PostImage.objects.filter(post_id=self.kwargs["post_pk"]).order_by("created_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["post"] = get_object_or_404(Post, pk=self.kwargs["post_pk"])
        return ctx
