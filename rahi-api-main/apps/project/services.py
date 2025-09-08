from __future__ import annotations
import datetime
import re
from typing import Optional

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response
from slugify import slugify

from apps.account.models import User
from apps.project import models
from apps.resume.models import Resume, Education

def _normalize(s: str) -> str:
    if not s:
        return ""
    return slugify(s, allow_unicode=True).replace("-", "").replace(" ", "").lower()


def get_primary_study_field(user) -> Optional[models.StudyField]:
    try:
        resume: Resume = getattr(user, "resume", None)
        if not resume:
            return None

        # Prefer explicitly finished latest; then fallback progressively
        qs = resume.educations.all().order_by("-end_date", "-start_date", "-created_at")
        edu: Optional[Education] = qs.first()
        return edu.field if edu else None
    except Exception:
        return None


def compute_project_relatability(project: models.Project, user) -> dict:
    sf = get_primary_study_field(user)
    if not sf:
        return {"score": 0, "matched_by": "none"}

    # ---- direct study_field overlap
    direct_match = 1.0 if project.study_fields.filter(id=sf.id).exists() else 0.0

    # ---- tag-category alignment with the study field (by normalized text)
    sf_key = _normalize(sf.title)
    tags = list(getattr(project, "tags").all())  # relies on prefetch in views
    total_tags = len(tags) or 1  # avoid div-by-zero
    def _hit(tag) -> bool:
        cat = getattr(tag, "category_ref", None)
        if not cat:
            return False
        # match by category code or title vs study field title
        return _normalize(cat.code) == sf_key or _normalize(cat.title) == sf_key

    hits = sum(1 for t in tags if _hit(t))
    category_match_ratio = hits / total_tags

    # ---- weighted score
    score = round((0.7 * direct_match + 0.3 * category_match_ratio) * 100)

    matched_by = "direct" if direct_match == 1.0 else ("category" if hits > 0 else "none")
    return {
        "score": score,
        "matched_by": matched_by,
        "debug": {
            "sf_id": str(sf.id),
            "sf_title": sf.title,
            "direct_match": direct_match,
            "category_hits": hits,
            "total_tags": total_tags if total_tags != 1 else (0 if len(tags) == 0 else 1),
        },
    }


def get_project_phase(project):
    if not project:
        return models.ProjectPhase.BEFORE_SELECTION
    return project.current_phase

def is_selection_phase_active(project=None):
    if project:
        return project.current_phase == models.ProjectPhase.SELECTION_ACTIVE
    
    # If no project specified, check if ANY project is in selection phase
    return models.Project.objects.filter(
        selection_phase=models.ProjectPhase.SELECTION_ACTIVE,
        is_active=True
    ).exists()

def can_show_attractiveness(project=None):
    if project:
        return project.show_attractiveness
    
    return models.Project.objects.filter(
        selection_phase__in=[
            models.ProjectPhase.SELECTION_ACTIVE,
            models.ProjectPhase.SELECTION_FINISHED
        ]
    ).exists()

def can_select_projects(project=None):
    if project:
        return project.can_be_selected
    
    return models.Project.objects.filter(
        selection_phase=models.ProjectPhase.SELECTION_ACTIVE,
        is_active=True,
        visible=True
    ).exists()

def count_project_attractiveness(project_id) -> int:
    from apps.project.models import ProjectAttractiveness
    return ProjectAttractiveness.objects.filter(project_id=project_id).count()

def get_projects_by_phase(phase=None):
    queryset = models.Project.objects.all()
    if phase:
        queryset = queryset.filter(selection_phase=phase)
    return queryset

def bulk_update_project_phases(project_ids, new_phase, update_dates=False, 
                               start_date=None, end_date=None):
    projects = models.Project.objects.filter(id__in=project_ids)
    
    update_fields = ['selection_phase']
    
    for project in projects:
        project.selection_phase = new_phase
        
        if update_dates:
            if start_date:
                project.selection_start = start_date
                update_fields.append('selection_start')
            if end_date:
                project.selection_end = end_date
                update_fields.append('selection_end')
    
    models.Project.objects.bulk_update(projects, update_fields)
    
    return projects.count()

def update_expired_project_phases():
    now = datetime.timezone.now()
    
    expired_projects = models.Project.objects.filter(
        auto_phase_transition=True,
        selection_phase=models.ProjectPhase.SELECTION_ACTIVE,
        selection_end__lt=now
    )
    
    count = expired_projects.update(selection_phase=models.ProjectPhase.SELECTION_FINISHED)
    return count

def activate_ready_projects():
    now = datetime.timezone.now()
    
    ready_projects = models.Project.objects.filter(
        auto_phase_transition=True,
        selection_phase=models.ProjectPhase.BEFORE_SELECTION,
        selection_start__lte=now,
        selection_end__gt=now
    )
    
    count = ready_projects.update(selection_phase=models.ProjectPhase.SELECTION_ACTIVE)
    return count

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
    requests = models.TeamRequest.objects.filter(user=user)
    state = False
    for request in requests:
        status = request.status
        if status == "A":
            state = True
            break
    return state

def user_team(user):
    from apps.project.models import TeamRequest

    team_request = TeamRequest.objects.filter(user=user, status="A").first()
    if team_request:
        return team_request.team.title

    return None

def allocate_project(excel_content):
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
