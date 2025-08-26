import datetime
import re

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response

from apps.account.models import User
from apps.project import models


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
