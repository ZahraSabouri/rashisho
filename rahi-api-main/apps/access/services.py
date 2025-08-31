# apps/access/services.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import re

from django.core.cache import cache
from django.contrib.auth.models import Group
from django.urls import resolve
from apps.access.models import AccessPolicy
from apps.access.domain import TeamRole
from apps.project.models import TeamRequest  # برای نقش تیمی 'C' و... از داده فعلی استفاده می‌شود. :contentReference[oaicite:3]{index=3}

CACHE_KEY = "access:policies:v1"
CACHE_TTL = 60  # ثانیه

@dataclass
class RequestContext:
    user: any
    view_name: str | None
    path: str
    method: str

def _load_policies():
    data = cache.get(CACHE_KEY)
    if data is not None:
        return data
    policies = list(AccessPolicy.objects.prefetch_related("roles").all())
    cache.set(CACHE_KEY, policies, CACHE_TTL)
    return policies

def invalidate_policy_cache():
    cache.delete(CACHE_KEY)

def _user_in_roles(user, groups: Iterable[Group]) -> bool:
    if not user.is_authenticated:
        return False
    if not groups:
        return True
    return user.groups.filter(id__in=[g.id for g in groups]).exists()

def _user_team_role(user) -> str | None:
    # اگر کاربر در تیمی با نقش خاص باشد از TeamRequest پیدا می‌شود (C=سرگروه و...). :contentReference[oaicite:4]{index=4}
    tr = TeamRequest.objects.filter(user=user, status="A").first()
    return tr.user_role if tr else None

def _eval_conditions(user, conditions: dict) -> bool:
    """
    پشتیبانی از ABAC پایه:
    - min_stage: حداقل مرحله مجاز (اگر UserScope داری، می‌توانی از آن بخوانی)
    - team_roles: لیست نقش‌های تیمی مجاز مثل ['C','M']
    - admin_sections: لیست بخش‌های ادمین که باید برای کاربر باز باشد (اگر UserAdminAccess داری)
    - region_cluster_ids/project_cluster_ids: می‌توانی با اسکوپ کاربر تطبیق دهی (اختیاری)
    """
    if not conditions:
        return True

    # نمونه‌ی سبک (می‌تونی با UserScope/Access سرویس کامل‌تر کنی)
    need_roles = conditions.get("team_roles")
    if need_roles:
        if _user_team_role(user) not in set(need_roles):
            return False
    # سایر شرط‌ها را در صورت وجود پیاده کن (min_stage, admin_sections, ...)
    return True

def is_allowed(ctx: RequestContext) -> bool:
    policies = _load_policies()
    for p in policies:
        # متد
        if p.methods and "*" not in p.methods and ctx.method not in p.methods:
            continue
        # منبع
        matched = False
        if p.resource_type == AccessPolicy.VIEW_NAME and ctx.view_name:
            matched = (p.resource == ctx.view_name)
        elif p.resource_type == AccessPolicy.PATH_REGEX:
            matched = bool(re.search(p.resource, ctx.path))
        if not matched:
            continue
        # نقش‌ها
        if not _user_in_roles(ctx.user, p.roles.all()):
            continue
        # شرط‌ها
        if not _eval_conditions(ctx.user, p.conditions or {}):
            continue
        return True
    return False
