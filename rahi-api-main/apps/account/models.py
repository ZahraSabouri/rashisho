import filetype
from django.contrib.auth.models import AbstractUser, Group, PermissionsMixin
from django.db import models
from django_resized import ResizedImageField
from rest_framework.exceptions import ValidationError

from apps.account.managers import BaseUserManager
from apps.common.models import BaseModel
from apps.settings.models import City


def default_user_info():
    return {
        "id": None,
        "first_name": None,
        "last_name": None,
        "national_id": None,
        "mobile_number": None,
    }


def personal_video_file_type(value):
    kind = filetype.guess(value.file.read())

    if kind is None:
        raise ValidationError("نوع فایل قابل شناسایی نیست.")

    mime_type = kind.mime

    allowed_types = [
        "video/mp4",
        "video/quicktime",
    ]

    if mime_type not in allowed_types:
        raise ValidationError("نوع فایل غیرمجاز است.")


class User(BaseModel, AbstractUser, PermissionsMixin):
    GENDER = [("FE", "زن"), ("MA", "مرد")]
    MILITARY_STATUS = [("EE", "معافیت تحصیلی"), ("PE", "معافیت دائم"), ("FS", "پایان خدمت"), ("IN", "مشمول")]
    MARTIAL_STATUS = [("SI", "مجرد"), ("MA", "متاهل")]

    bio = models.TextField()
    user_info = models.JSONField(default=default_user_info)
    avatar = ResizedImageField(size=[250, 250], crop=["middle", "center"], upload_to="account/avatar", blank=True)
    personal_video = models.FileField(
        upload_to="account/personal_video", validators=[personal_video_file_type], null=True, blank=True
    )
    city = models.ForeignKey(City, on_delete=models.CASCADE, null=True, verbose_name="شهر")
    address = models.TextField(verbose_name="آدرس")
    birth_date = models.DateField(null=True, verbose_name="تاریخ تولد")
    gender = models.CharField(max_length=2, choices=GENDER, verbose_name="جنسیت")
    military_status = models.CharField(
        max_length=2, null=True, blank=True, choices=MILITARY_STATUS, verbose_name="وضعیت نظام وظیفه"
    )
    marriage_status = models.CharField(max_length=2, choices=MARTIAL_STATUS, verbose_name="وضعیت تاهل")
    community = models.ForeignKey(
        "community.Community",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="انجمن",
    )
    telegram_address = models.CharField(max_length=100, null=True, blank=True, verbose_name="آدرس تلگرام")

    objects = BaseUserManager()

    is_accespted_terms = models.BooleanField(verbose_name="آیا قوانین مسابقه را قبول کرده است؟", default=False)

    @property
    def mobile_number(self):
        return self.user_info["mobile_number"]

    @property
    def full_name(self):
        return f"{self.user_info.get("first_name")} {self.user_info.get("last_name")}"

    @property
    def user_id(self):
        return self.user_info["id"]

    @property
    def role(self):
        group = self.groups.last()

        if not group:
            user_group = Group.objects.get(name="کاربر")
            self.groups.add(user_group.id)
            self.save()
            return 1

        if group.name == "ادمین":
            return 0
        else:
            return 1

    @user_id.setter
    def user_id(self, value):
        self.user_info["id"] = value

    def has_role(self, groups: list[str]) -> bool:
        for group in groups:
            if Group.objects.filter(name=group, user=self).exists():
                return True
        return False

    def __str__(self) -> str:
        return f"{self.full_name}"


class Connection(BaseModel):
    """
    Connection model:
    - Represents a user-to-user connection request
    - Contains status: pending, accepted, rejected
    - Once accepted, both users can see each other's phone number
    """
    STATUS_CHOICES = [
        ("pending", "در انتظار"),
        ("accepted", "پذیرفته شده"),
        ("rejected", "رد شده"),
    ]

    from_user = models.ForeignKey(
        "User",
        related_name="connections_sent",
        on_delete=models.CASCADE,
        verbose_name="کاربر درخواست‌دهنده"
    )
    to_user = models.ForeignKey(
        "User",
        related_name="connections_received",
        on_delete=models.CASCADE,
        verbose_name="کاربر دریافت‌کننده"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="وضعیت"
    )

    class Meta(BaseModel.Meta):
        verbose_name = "ارتباط"
        verbose_name_plural = "ارتباط‌ها"
        unique_together = ("from_user", "to_user")

    def __str__(self):
        return f"{self.from_user} → {self.to_user} ({self.status})"
