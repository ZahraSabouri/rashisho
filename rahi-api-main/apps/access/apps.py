# apps/access/apps.py
from django.apps import AppConfig

class AccessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.access"   # مسیر کامل ماژول
    label = "access"       # لیبل یکتا (اختیاری اما خوبه)
