from django.shortcuts import get_object_or_404
from rest_framework import mixins, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.api.permissions import IsAdminOrReadOnlyPermission  # house perm
from apps.api.schema import TaggedAutoSchema
from apps.blog.models import Post, PostImage
from apps.blog.api.serializers.post import PostSerializer, PostImageSerializer

class PostViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Blog"])
    queryset = Post.objects.all().order_by("-created_at")
    serializer_class = PostSerializer
    permission_classes = [IsAdminOrReadOnlyPermission]  # read for all, write admin only
    ordering_fields = ["created_at", "updated_at", "title"]

class PostImageViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    schema = TaggedAutoSchema(tags=["Blog"])
    serializer_class = PostImageSerializer
    permission_classes = [IsAdminOrReadOnlyPermission]

    def get_queryset(self):
        return PostImage.objects.filter(post_id=self.kwargs["post_pk"]).order_by("created_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["post"] = get_object_or_404(Post, pk=self.kwargs["post_pk"])
        return ctx

    @extend_schema(
        tags=["Blog"],
        request=PostImageSerializer,
        responses={201: PostImageSerializer, 400: OpenApiResponse(description="Too many images")},
        description="Upload an extra image for a blog post (max 10).",
    )
    def create(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=self.kwargs["post_pk"])
        if post.images.count() >= 10:
            return Response({"detail": "حداکثر ۱۰ تصویر مجاز است."}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)
