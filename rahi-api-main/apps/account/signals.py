from django.conf import settings
from django.dispatch import receiver
from django.apps import apps
from django.db.models.signals import post_save, pre_save
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.db import models

from apps.account.models import User
from apps.public.models import UserNotification
from apps.resume.models import Connection

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


@receiver(pre_save, sender=User)
def track_email_change(sender, instance, **kwargs):
    """Track email changes to send notifications"""
    if instance.pk:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            instance._email_changed = old_instance.email != instance.email
            instance._old_email = old_instance.email
        except User.DoesNotExist:
            instance._email_changed = False
    else:
        instance._email_changed = False


@receiver(post_save, sender=User)
def handle_email_change(sender, instance, created, **kwargs):
    """Send notifications when راه ارتباطی (email) changes"""
    
    if created:
        # New user - send welcome notification about راه ارتباطی
        UserNotification.objects.create(
            user=instance,
            title="راه ارتباطی شما تنظیم شد",
            body=f"ایمیل شما ({instance.email}) به عنوان راه ارتباطی اصلی تنظیم شد. "
                  "سایر کاربران پس از تأیید درخواست ارتباط، این ایمیل را مشاهده خواهند کرد.",
            kind="info",
            url="/profile/edit/"
        )
        return

    # Check if email changed
    if hasattr(instance, '_email_changed') and instance._email_changed:
        old_email = getattr(instance, '_old_email', '')
        new_email = instance.email
        
        # 1. Send notification to user about their email change
        UserNotification.objects.create(
            user=instance,
            title="راه ارتباطی شما تغییر کرد",
            body=f"راه ارتباطی شما از {old_email} به {new_email} تغییر یافت. "
                  "اتصالات فعلی شما همچنان فعال هستند.",
            kind="info",
            url="/profile/edit/"
        )
        
        # 2. Send email to user's old email (if exists)
        if old_email:
            try:
                send_mail(
                    subject="تغییر راه ارتباطی در راهی‌شو",
                    message=f"""
                    سلام {instance.get_full_name()},
                    
                    راه ارتباطی حساب کاربری شما در پلتفرم راهی‌شو تغییر یافت.
                    
                    ایمیل قبلی: {old_email}
                    ایمیل جدید: {new_email}
                    
                    اگر این تغییر توسط شما انجام نشده، لطفا با پشتیبانی تماس بگیرید.
                    
                    تیم راهی‌شو
                    """,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[old_email],
                    fail_silently=True,
                )
            except Exception as e:
                # Log error but don't fail the user update
                print(f"Failed to send email change notification: {e}")
        
        # 3. Send email to user's new email
        if new_email:
            try:
                send_mail(
                    subject="راه ارتباطی جدید در راهی‌شو تأیید شد",
                    message=f"""
                    سلام {instance.get_full_name()},
                    
                    ایمیل جدید شما ({new_email}) به عنوان راه ارتباطی اصلی در راهی‌شو تنظیم شد.
                    
                    از این پس:
                    - سایر شرکت‌کنندگان پس از تأیید درخواست ارتباط، این ایمیل را خواهند دید
                    - اطلاعیه‌های مهم به این ایمیل ارسال می‌شود
                    
                    تیم راهی‌شو
                    """,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[new_email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Failed to send new email confirmation: {e}")
        
        # 4. Notify users who have active connections with this user
        active_connections = Connection.objects.filter(
            models.Q(from_user=instance) | models.Q(to_user=instance),
            status='accepted'
        )
        
        for connection in active_connections:
            other_user = connection.to_user if connection.from_user == instance else connection.from_user
            UserNotification.objects.create(
                user=other_user,
                title="راه ارتباطی یکی از مخاطبین تغییر کرد",
                body=f"راه ارتباطی {instance.get_full_name()} تغییر یافت. "
                      f"ایمیل جدید: {new_email}",
                kind="info",
                url=f"/profile/{instance.id}/"
            )
