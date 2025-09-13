import filetype
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import models
from rest_framework.exceptions import ValidationError

from apps.common.models import BaseModel
from apps.utils.utility import mobile_validator

Ticket_STATUS = [("OPEN", "open"), ("CLOSED", "closed")]
USER_ROLE = [("ADMIN", "admin"), ("USER", "user")]


def validate_ticket_file(value):
    valid_types = [
        "video/mp4",
        "video/webm",
        "video/mov",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/jfif",
    ]

    kind = filetype.guess(value.file.read())

    if kind is None:
        raise ValidationError("نوع فایل قابل شناسایی نیست.")

    mime_type = kind.mime
    if mime_type not in valid_types:
        raise ValidationError("نوع فایل غیرمجاز است.")


class Notification(BaseModel):
    title = models.CharField(max_length=255, verbose_name="عنوان")
    description = models.TextField(verbose_name="توضیحات")
    image = models.ImageField(upload_to="notifications/images", verbose_name="تصویر")

    class Meta(BaseModel.Meta):
        verbose_name = "اطلاعیه"
        verbose_name_plural = "اطلاعیه ها"

    def __str__(self):
        return self.title


class CommonQuestions(models.Model):
    question = models.TextField(verbose_name="سوال")
    answer = models.TextField(verbose_name="پاسخ")

    class Meta:
        verbose_name = "سوالات متداول"
        verbose_name_plural = "سوالات متداول"

    def __str__(self):
        return self.question


class ContactInformation(models.Model):
    address = models.TextField(null=True, blank=True, verbose_name="آدرس")
    contact_number = models.CharField(null=True, blank=True, max_length=11, verbose_name="شماره تماس")
    telegram = models.CharField(null=True, blank=True, verbose_name="تلگرام")
    linked_in = models.CharField(null=True, blank=True, verbose_name="لینکداین")
    instagram = models.CharField(null=True, blank=True, verbose_name="اینستاگرام")

    class Meta:
        verbose_name = "اطلاعات تماس"
        verbose_name_plural = "اطلاعات تماس"


class AboutUs(models.Model):
    description = models.TextField(verbose_name="توضیحات")
    image = models.ImageField(null=True, upload_to="public/about_us", verbose_name="تصویر")

    class Meta:
        verbose_name = "درباره ما"
        verbose_name_plural = "درباره ما"

    def __str__(self):
        return self.description


class CompetitionRule(models.Model):
    description = models.TextField(verbose_name="توضیحات")

    class Meta:
        verbose_name = "قانون مسابقه"
        verbose_name_plural = "قوانین مسابقه"

    def __str__(self):
        return self.description


class ContactUs(BaseModel):
    full_name = models.CharField(max_length=50, verbose_name="نام و نام خانوادگی")
    email = models.EmailField(verbose_name="آدرس ایمیل")
    mobile_number = models.CharField(max_length=11, null=True, validators=[mobile_validator], verbose_name="شماره تماس")
    message_title = models.CharField(max_length=50, verbose_name="موضوع پیام")
    message_body = models.TextField(verbose_name="متن پیام")

    class Meta(BaseModel.Meta):
        verbose_name = "تماس با ما"
        verbose_name_plural = "تماس با ما"

    def __str__(self):
        return self.full_name


class Footer(models.Model):
    description = models.TextField(verbose_name="توضیحات")

    class Meta:
        verbose_name = "پاورقی"
        verbose_name_plural = "پاورقی"

    def __str__(self):
        return self.description[:20]


class Department(BaseModel):
    title = models.CharField(max_length=200, verbose_name="عنوان")

    class Meta(BaseModel.Meta):
        verbose_name = "دپارتمان"
        verbose_name_plural = "دپارتمان ها"

    def __str__(self):
        return self.title


class Ticket(models.Model):
    title = models.CharField(max_length=255, null=True, verbose_name="عنوان")
    status = models.CharField(max_length=6, choices=Ticket_STATUS, verbose_name="وضعیت")
    department = models.ForeignKey(
        Department, null=True, on_delete=models.PROTECT, related_name="tickets", verbose_name="دپارتمان"
    )
    created_at = models.DateTimeField(null=True, auto_now_add=True, verbose_name="تاریخ ایجاد تیکت")

    class Meta:
        verbose_name = "تیکت"
        verbose_name_plural = "تیکت ها"

    def __str__(self):
        return f"{self.user.full_name} | {self.title} | {self.get_status_display()}"

    @property
    def user(self):
        return self.comments.filter(user_role="USER").first().user


class Comment(BaseModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name="comments", verbose_name="تیکت")
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name="comments", verbose_name="کاربر")
    user_role = models.CharField(max_length=5, choices=USER_ROLE, null=True, verbose_name="نقش کاربر")
    description = models.TextField(verbose_name="توضیحات")
    file = models.FileField(validators=[validate_ticket_file], null=True, blank=True, verbose_name="فایل")

    class Meta(BaseModel.Meta):
        verbose_name = "سوال"
        verbose_name_plural = "سوال ها"

    def __str__(self):
        return f"{self.user.full_name} | {self.ticket.get_status_display()}"


class UserNotification(BaseModel):
    KINDS = [
        ("TEAM_INVITE", "دعوت تیم"),
        ("INFO", "اطلاع‌رسانی"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    kind = models.CharField(max_length=32, choices=KINDS, default="INFO")
    payload = models.JSONField(default=dict, blank=True)  # e.g. {"team_id": "...", "team_title": "..."}
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        verbose_name = "اعلان کاربر"
        verbose_name_plural = "اعلانات کاربران"
        ordering = ("-created_at",)