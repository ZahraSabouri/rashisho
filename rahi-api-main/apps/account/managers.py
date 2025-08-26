from typing import Any

from django.contrib.auth.models import UserManager

from apps.common.models import BaseManager


class BaseUserManager(BaseManager, UserManager):
    def create_superuser(self, username: str, email: str | None, password: str | None, **extra_fields: Any) -> Any:
        return super().create_superuser(username, email, password, **extra_fields)
