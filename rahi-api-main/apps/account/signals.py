from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_welcome_notification(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        UserNotification = apps.get_model("public", "UserNotification")
        UserNotification.objects.create(
            user=instance,
            kind="INFO",
            title="خوش آمدید به راهی‌شو",
            body="پروفایل‌تان را تکمیل کنید تا تیم‌ها شما را بهتر ببینند.",
            url="/dashboard",
        )
    except Exception:
        pass
