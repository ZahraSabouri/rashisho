import filetype
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import models
from django.utils import timezone
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


class Announcement(BaseModel):
    title = models.CharField(max_length=255, verbose_name="عنوان")
    description = models.TextField(verbose_name="توضیحات")
    image = models.ImageField(upload_to="announcements/images", verbose_name="تصویر")
    is_active = models.BooleanField(default=False, verbose_name="فعال؟")
    target_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, verbose_name="کاربران هدف")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="announcements_created",
        verbose_name="ایجادکننده"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="notifications_created",
        verbose_name="ایجادکننده"
    )


    class Meta(BaseModel.Meta):
        verbose_name = "اعلان"
        verbose_name_plural = "اعلانات"

    def __str__(self):
        return self.title
    
    def is_targeted_to_user(self, user):
        if not self.target_users.exists():
            return True  # No specific targeting = show to all users
        return self.target_users.filter(id=user.id).exists()
    


class AnnouncementReceipt(BaseModel):  # Previously NotificationReceipt
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="receipts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcement_receipts")
    acknowledged_at = models.DateTimeField(null=True, blank=True)  # "Got it"
    snoozed_until = models.DateTimeField(null=True, blank=True)    # "Remind later"

    class Meta(BaseModel.Meta):
        verbose_name = "وضعیت اعلان‌های کاربر"
        verbose_name_plural = "وضعیت اعلان‌های کاربران"
        constraints = [
            models.UniqueConstraint(fields=["announcement", "user"], name="unique_announcement_receipt_per_user")
        ]

    def is_suppressed_now(self) -> bool:
        """True if user has acknowledged or is currently snoozed."""
        if self.acknowledged_at:
            return True  # User clicked "Got it" - never show again
        
        if self.snoozed_until and self.snoozed_until > timezone.now():
            return True  # User is still in snooze period
        
        return False


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
    url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "آگهی کاربر"
        verbose_name_plural = "آگهی‌های کاربر"
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
        ]

    def mark_read(self):
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])


# class Announcement(BaseModel):
#     title = models.CharField(max_length=200)
#     body  = models.TextField()
#     active = models.BooleanField(default=False)

#     class Meta(BaseModel.Meta):
#         verbose_name = "اعلان ورود"
#         verbose_name_plural = "اعلان‌های ورود"

class UserAnnouncementState(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE)
    got_it = models.BooleanField(default=False)  # True => don't show again

    class Meta(BaseModel.Meta):
        unique_together = ("user", "announcement")
