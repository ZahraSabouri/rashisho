from __future__ import annotations
import datetime
import re

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response

from apps.account.models import User
from apps.project import models


# ---------------- project attractiveness selection phase services

def get_project_phase(project):
    """
    Get current phase for a specific project.
    Uses project.current_phase property which handles auto-calculation.
    """
    if not project:
        return models.ProjectPhase.BEFORE_SELECTION
    return project.current_phase

def is_selection_phase_active(project=None):
    """
    Check if selection is active for a project.
    For backward compatibility, can be called without project.
    """
    if project:
        return project.current_phase == models.ProjectPhase.SELECTION_ACTIVE
    
    # If no project specified, check if ANY project is in selection phase
    return models.Project.objects.filter(
        selection_phase=models.ProjectPhase.SELECTION_ACTIVE,
        is_active=True
    ).exists()

def can_show_attractiveness(project=None):
    """
    Should attractiveness count be visible for this project?
    Shows during SELECTION_ACTIVE and SELECTION_FINISHED phases.
    """
    if project:
        return project.show_attractiveness
    
    # Global check - show if any project allows it
    return models.Project.objects.filter(
        selection_phase__in=[
            models.ProjectPhase.SELECTION_ACTIVE,
            models.ProjectPhase.SELECTION_FINISHED
        ]
    ).exists()

def can_select_projects(project=None):
    """
    Can users currently select this project?
    Only during SELECTION_ACTIVE phase.
    """
    if project:
        return project.can_be_selected
    
    # Global check
    return models.Project.objects.filter(
        selection_phase=models.ProjectPhase.SELECTION_ACTIVE,
        is_active=True,
        visible=True
    ).exists()

def count_project_attractiveness(project_id) -> int:
    """
    Count how many users selected this project at any priority.
    Uses normalized ProjectSelection table for fast counting.
    """
    from apps.project.models import ProjectSelection
    return ProjectSelection.objects.filter(project_id=project_id).count()

def get_projects_by_phase(phase=None):
    """Get projects filtered by phase"""
    queryset = models.Project.objects.all()
    if phase:
        queryset = queryset.filter(selection_phase=phase)
    return queryset

def bulk_update_project_phases(project_ids, new_phase, update_dates=False, 
                               start_date=None, end_date=None):
    """
    Bulk update project phases.
    Useful for management commands or admin actions.
    """
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
    
    # Bulk update for performance
    models.Project.objects.bulk_update(projects, update_fields)
    
    return projects.count()

def update_expired_project_phases():
    """
    Update projects that should auto-transition to FINISHED phase.
    Call this in a periodic task or management command.
    """
    now = datetime.timezone.now()
    
    expired_projects = models.Project.objects.filter(
        auto_phase_transition=True,
        selection_phase=models.ProjectPhase.SELECTION_ACTIVE,
        selection_end__lt=now
    )
    
    count = expired_projects.update(selection_phase=models.ProjectPhase.SELECTION_FINISHED)
    return count

def activate_ready_projects():
    """
    Activate projects that should transition to SELECTION_ACTIVE phase.
    Call this in a periodic task or management command.
    """
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
