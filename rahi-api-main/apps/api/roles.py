# apps/api/roles.py  (بروزرسانی)
from django.contrib.auth.models import Group
from apps.utils.cache import Cache

class SetUpRole:
    def __init__(self) -> None:
        user, _ = Group.objects.get_or_create(name="کاربر")
        sysgod, _ = Group.objects.get_or_create(name="ادمین")
        expert, _ = Group.objects.get_or_create(name="کارشناس")  # جدید

        Cache.set_cache("user", user)
        Cache.set_cache("sys_god", sysgod)
        Cache.set_cache("expert", expert)

class Roles:
    user = Cache.get_cache("user")
    sys_god = Cache.get_cache("sys_god")
    expert = Cache.get_cache("expert")
