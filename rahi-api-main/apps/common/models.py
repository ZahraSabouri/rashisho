import uuid
from typing import Any

from django.db import models
from django.utils import timezone

from apps.common.managers import BaseManager


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    deleted = models.BooleanField(default=False, editable=False)

    SOFT_DELETE = False

    objects = BaseManager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def delete(self, using: Any = None, keep_parents: bool = False) -> Any:
        if self.SOFT_DELETE:
            self.deleted = True
            self.deleted_at = timezone.now()
            self.save()
        else:
            return super().delete(using, keep_parents)
