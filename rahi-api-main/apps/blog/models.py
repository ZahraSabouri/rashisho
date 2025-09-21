from django.db import models
from apps.common.models import BaseModel

class Post(BaseModel):
    title = models.CharField(max_length=255, verbose_name="عنوان")
    image = models.ImageField(upload_to="blog/images", verbose_name="تصویر اصلی")
    video = models.FileField(upload_to="blog/videos", null=True, blank=True, verbose_name="ویدیو")
    content = models.TextField(verbose_name="محتوای HTML (ریچ تکست)")

    # M2M to projects; limit (<=3) enforced in serializer
    related_projects = models.ManyToManyField(
        "project.Project", blank=True, related_name="related_blog_posts", verbose_name="پروژه‌های مرتبط"
    )

    class Meta(BaseModel.Meta):
        verbose_name = "پست وبلاگ"
        verbose_name_plural = "پست‌های وبلاگ"

    def __str__(self) -> str:
        return self.title


class PostImage(BaseModel):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="blog/post_images", verbose_name="تصویر")

    class Meta(BaseModel.Meta):
        verbose_name = "تصویر پست"
        verbose_name_plural = "تصاویر پست"

    def __str__(self) -> str:
        return f"{self.post_id} - image {self.id}"
