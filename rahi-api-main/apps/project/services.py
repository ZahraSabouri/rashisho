from __future__ import annotations
import datetime
import re

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response

from apps.account.models import User
from apps.project import models

from typing import Iterable, Optional
from django.db.models import Q
from django.core.cache import cache
from django.apps import apps as django_apps

# from apps.project.models import ProjectAllocation
from apps.settings.models import FeatureActivation

CACHE_TTL = 60  # seconds
CACHE_PREFIX = "proj_attr_count:" 


def _cache_key(project_id) -> str:
    return f"{CACHE_PREFIX}{project_id}"


def invalidate_attractiveness(project_ids: Iterable[str | int]) -> None:
    """
    Delete cache entries for all given project IDs.
    Accepts str/UUID/int; turns them into strings for cache keys.
    """
    for pid in project_ids:
        cache.delete(_cache_key(str(pid)))

def is_selection_phase_active() -> bool:
    return FeatureActivation.objects.filter(feature="PP", active=True).exists()

def count_project_attractiveness(project_id) -> int:
    """
    Count how many participants have selected the project at ANY priority slot.
    Lazily fetch ProjectAllocation to avoid circular import with models.py
    """
    # Lazy import to avoid: models -> services -> models cycle
    ProjectAllocation = django_apps.get_model("project", "ProjectAllocation")  # <— NEW

    cache_key = f"proj_attr_count:{project_id}"
    cached: Optional[int] = cache.get(cache_key)
    if cached is not None:
        return cached

    q = (
        Q(priority__1=str(project_id))
        | Q(priority__2=str(project_id))
        | Q(priority__3=str(project_id))
        | Q(priority__4=str(project_id))
        | Q(priority__5=str(project_id))
    )
    cnt = ProjectAllocation.objects.filter(q).count()
    cache.set(cache_key, cnt, CACHE_TTL)
    return cnt

def generate_project_unique_code():
    now = datetime.datetime.now()
    year = now.year
    month = now.strftime("%m")

    last_project = models.Project.objects.first()
    if not last_project:
        unique_code = 1
    else:
        previous_code = last_project.code.split("/")[2]
        unique_code = int(previous_code) + 1

    return f"{year}/{month}/{unique_code:04d}"


def is_team_member(user):
    """If user is a team member, return True, else return False"""

    requests = models.TeamRequest.objects.filter(user=user)
    state = False
    for request in requests:
        status = request.status
        if status == "A":
            state = True
            break
    return state


def user_team(user):
    """Here we return the user team name if he/she has team"""

    from apps.project.models import TeamRequest

    team_request = TeamRequest.objects.filter(user=user, status="A").first()
    if team_request:
        return team_request.team.title

    return None


def allocate_project(excel_content):
    """Allocate projects to users."""
    from apps.project.api.serializers import project as serializers

    errors_count = []

    for index, row in excel_content.iterrows():
        user = User.objects.filter(user_info__national_id=str(row.iloc[0])).first()
        project = models.Project.objects.filter(code=str(row.iloc[1])).first()

        if project and user:
            project_allocation = models.ProjectAllocation.objects.filter(user=user).first()
            data = {"project": project.id}
            allocation_serializer = serializers.ProjectAllocationSerializer(
                instance=project_allocation, data=data, partial=True
            )
            if allocation_serializer.is_valid():
                allocation_serializer.save()
            else:
                errors_count.append(index + 2)
        else:
            errors_count.append(index + 2)
            continue

    if errors_count:
        return Response(
            {"detail": f"خطایی در ذخیره سازی رکوردهای سطر {errors_count} به وجود آمد!"}, status=status.HTTP_200_OK
        )

    return Response({"detail": "عملیات موفقیت آمیز بود!"}, status=status.HTTP_200_OK)


def validate_persian(value):
    persian_regex = re.compile(r"^[\u0600-\u06FF\u0750-\u077F\s]+$")
    if not persian_regex.match(value):
        raise ValidationError(
            "فقط کارکترهای فارسی مجاز می باشد.",
            params={"value": value},
        )
