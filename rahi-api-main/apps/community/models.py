from django.db import models

from apps.common.models import BaseModel


class Community(BaseModel):
    title = models.CharField(max_length=400, verbose_name="نام انجمن")
    code = models.CharField(max_length=6, unique=True, verbose_name="کد انجمن")
    manager = models.OneToOneField(
        "account.User",
        on_delete=models.PROTECT,
        related_name="created_communities",
        null=True,
        verbose_name="مدیر انجمن",
    )
    representer_community = models.ForeignKey(
        "Community",
        related_name="represented_communities",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="انجمن معرف",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "انجمن علمی"
        verbose_name_plural = "انجمن های علمی"

    def __str__(self):
        return self.title


class CommunityResource(BaseModel):
    title = models.CharField(max_length=200, verbose_name="عنوان")
    file = models.FileField(upload_to="community/file", verbose_name="فایل")
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="resources", verbose_name="انجمن")

    class Meta(BaseModel.Meta):
        verbose_name = "فایل انجمن"
        verbose_name_plural = "فایل های انجمن"

    def __str__(self):
        return self.title
