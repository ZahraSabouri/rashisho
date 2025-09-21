from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.blog.api.views.post import PostViewSet, PostImageViewSet

app_name = "blog"

router = DefaultRouter()
router.register("posts", PostViewSet, basename="posts")

urlpatterns = [
    path("", include(router.urls)),
    path("posts/<uuid:post_pk>/images/", PostImageViewSet.as_view({"get": "list", "post": "create"}), name="post-images"),
    path("posts/<uuid:post_pk>/images/<uuid:pk>/", PostImageViewSet.as_view({"delete": "destroy"}), name="post-image"),
]
