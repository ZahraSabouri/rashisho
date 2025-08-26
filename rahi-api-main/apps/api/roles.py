from django.conf import settings
from django.contrib.auth.models import Group

from apps.utils.cache import Cache


class SetUpRole:
    def __init__(self) -> None:
        if not settings.IS_TEST:
            user, _ = Group.objects.get_or_create(name="کاربر")
            sysgod, _ = Group.objects.get_or_create(name="ادمین")
            Cache.set_cache("user", user)
            Cache.set_cache("sys_god", sysgod)


class Roles:
    user: Group = Cache.get_cache("user")
    sys_god: Group = Cache.get_cache("sys_god")
