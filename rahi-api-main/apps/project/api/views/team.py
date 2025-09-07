import functools

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet

from apps.account.api.serializers.user import UserBriefInfoSerializer
from apps.api.permissions import IsSysgod, IsUser
from apps.project import models
from apps.project.api.serializers import team
from apps.project.models import Team
from apps.resume.models import Resume

from apps.api.schema import TaggedAutoSchema

class ProjectParticipantsViewSet(ReadOnlyModelViewSet):
    schema = TaggedAutoSchema(tags=["Team"])
    serializer_class = team.TeammateInfoSerializer
    permission_classes = [IsUser | IsSysgod]

    def get_serializer_class(self):
        state = self.kwargs.get("state", None)
        if state == "brief":
            return UserBriefInfoSerializer
        return super().get_serializer_class()

    def get_serializer_context(self):
        result = super().get_serializer_context()
        result["requested_user"] = self.request.user
        return result

    def get_queryset(self):
        """Here we return a list of users who have participated in a project that this user is involved in."""

        if self.action == "get_paginated_users_team_request":
            _user = self._user()
            user_allocation = models.ProjectAllocation.objects.filter(user=_user).first()

            if not user_allocation or user_allocation and not user_allocation.project:
                return Response({"message": "هنوز به شما پروژه ای اختصاص داده نشده است!"}, status=status.HTTP_200_OK)

            allocations = models.ProjectAllocation.objects.filter(project=user_allocation.project).exclude(
                user=_user.id
            )
            users = get_user_model().objects.filter(project__in=allocations)
            team_requests = models.TeamRequest.objects.filter(user__in=users).exclude(user_role="C").values("user")
            if not team_requests:
                return users

            users_in_team_request = get_user_model().objects.filter(id__in=team_requests)
            users_with_same_project = users.exclude(id__in=team_requests)
            final_users = users_in_team_request | users_with_same_project

            return final_users

        _user = self._user()
        user_allocation = models.ProjectAllocation.objects.filter(user=_user).first()
        if not user_allocation:
            return get_user_model().objects.none()

        allocations = models.ProjectAllocation.objects.filter(project=user_allocation.project).exclude(user=_user.id)
        users = get_user_model().objects.filter(project__in=allocations)
        team_requests = (
            models.TeamRequest.objects.filter(user__in=users).exclude(Q(user_role="C") | Q(status="A")).values("user")
        )
        if not team_requests:
            return users

        user_list = get_user_model().objects.filter(id__in=team_requests)
        return user_list

    @functools.cache
    def _user(self):
        return self.request.user

    @action(
        methods=["GET"], detail=False, url_path="users-status", serializer_class=team.UsersTeamRequestStatusSerializer
    )
    def users_team_request_status(self, request, *args, **kwargs):
        """Returns the users with same project and their request status that this user if sent them"""

        _user = self._user()
        user_allocation = models.ProjectAllocation.objects.filter(user=_user).first()

        if not user_allocation or user_allocation and not user_allocation.project:
            return Response({"message": "هنوز به شما پروژه ای اختصاص داده نشده است!"}, status=status.HTTP_200_OK)

        allocations = models.ProjectAllocation.objects.filter(project=user_allocation.project).exclude(user=_user.id)
        users = get_user_model().objects.filter(project__in=allocations)
        team_requests = models.TeamRequest.objects.filter(user__in=users).exclude(user_role="C").values("user")
        if not team_requests:
            serializer = self.serializer_class(users, many=True, context={"requested_user": self._user()})
            return Response(serializer.data)

        users_in_team_request = get_user_model().objects.filter(id__in=team_requests)
        users_with_same_project = users.exclude(id__in=team_requests)
        final_users = users_in_team_request | users_with_same_project
        serializer = self.serializer_class(final_users, many=True, context={"requested_user": self._user()})

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(["GET"], detail=False)
    def get_paginated_users_team_request(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class TeamBuildViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Team"])
    serializer_class = team.TeamSerializer
    queryset = models.Team.objects.all()
    permission_classes = [IsUser | IsSysgod]
    filterset_fields = "__all__"

    def perform_create(self, serializer):
        user_allocate = models.ProjectAllocation.objects.filter(user=self._user()).first()
        if not user_allocate:
            raise ValidationError("هنوز به این کاربر پروژه ای اختصاص داده نشده است!")

        project = user_allocate.project
        created_team = serializer.save(project=project)
        models.TeamRequest.objects.create(user=self._user(), team=created_team, user_role="C", status="A")

    def perform_destroy(self, instance: models.Team):
        request: models.TeamRequest = instance.requests.filter(user=self._user(), team=instance).first()
        if request.user_role != "C":
            raise ValidationError("شما اجازه حذف این تیم را ندارید!")

        super().perform_destroy(instance)

    def _user(self):
        return self.request.user


class MyTeamAPV(APIView):
    schema = TaggedAutoSchema(tags=["Team"])
    serializer_class = team.TeamSerializer
    permission_classes = [IsUser | IsSysgod]

    def get(self, request, *args, **kwargs):
        _user = self.request.user
        user_request = models.TeamRequest.objects.filter(user=_user, status="A").first()
        if not user_request:
            raise ValidationError("شما تیم ندارید!")

        return Response(self.serializer_class(user_request.team).data, status=status.HTTP_200_OK)


class TeamRequestViewSet(
    mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, mixins.ListModelMixin, GenericViewSet
):
    schema = TaggedAutoSchema(tags=["Team"])
    serializer_class = team.TeamRequestSerializer
    queryset = models.TeamRequest.objects.all()
    permission_classes = [IsUser | IsSysgod]
    filterset_fields = "__all__"

    def get_queryset(self):
        requests = models.TeamRequest.objects.filter(user=self._user()).exclude(user_role="C")
        return requests

    def _user(self):
        return self.request.user

    @action(methods=["POST"], detail=False, url_path="cancel-request")
    def cancel_request(self, request, *args, **kwargs):
        user_id = self.request.data.get("user")
        team_id = self.request.data.get("team")
        if not models.TeamRequest.objects.filter(user=self._user(), team_id=team_id, user_role="C").exists():
            raise ValidationError("شما تیمی ایجاد نکرده اید!")

        request = models.TeamRequest.objects.filter(
            user__user_info__id=user_id, team_id=team_id, user_role="M", status="W"
        ).first()
        if not request:
            raise ValidationError("درخواستی برای این کاربر وجود ندارد!")

        request.delete()
        return Response({"message": "عملیات با موفقیت انجام شد."}, status=status.HTTP_200_OK)

    @action(methods=["POST"], detail=False, url_path="send-request")
    def send_request(self, request, *args, **kwargs):
        user_id = self.request.data.get("user")
        team_id = self.request.data.get("team")
        user_team = models.TeamRequest.objects.filter(user=self._user(), team_id=team_id, user_role="C")
        if not user_team.exists():
            raise ValidationError("شما تیمی ایجاد نکرده اید!")

        user = get_user_model().objects.filter(user_info__id=user_id).first()
        if models.TeamRequest.objects.filter(user=user, team_id=team_id, user_role="M").exists():
            raise ValidationError("درخواست هم تیمی برای این کاربر، قبلا ارسال شده است!")

        try:
            models.TeamRequest.objects.create(user=user, team_id=team_id, user_role="M", status="W")

        except Exception:
            raise ValidationError("خطایی در ارسال درخواست هم تیمی رخ داده است!")

        return Response({"message": "عملیات با موفقیت انجام شد."}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="is-team-created")
    def is_team_created(self, request, *args, **kwargs):
        """Here we return status for team creation and the user role in team"""

        user_request = models.TeamRequest.objects.filter(user=self._user(), status="A").first()
        if not user_request:
            return Response({"status": None}, status=status.HTTP_200_OK)

        user_team = user_request.team
        user_role = user_request.get_user_role_display()
        accepted_requests = models.TeamRequest.objects.filter(team=user_team, status="A").count()
        if accepted_requests >= 2:
            return Response({"status": "team created", "user_role": user_role}, status=status.HTTP_200_OK)

        return Response({"status": "team not created", "user_role": user_role}, status=status.HTTP_200_OK)


class TeamInfoAPV(APIView):
    schema = TaggedAutoSchema(tags=["Team"])
    permission_classes = [IsSysgod]

    def get(self, request, *args, **kwargs):
        team_id = request.query_params["team_id"]
        if not team_id:
            return Response(
                {"message": "خطا، اطلاعات تیم مشکل دارد، دوباره سعی کنید"}, status=status.HTTP_400_BAD_REQUEST
            )

        final_data = {}
        # set basic team info to final data
        team = Team.objects.get(id=team_id)
        final_data["title"] = team.title
        final_data["description"] = team.description
        final_data["project_title"] = team.project.title
        final_data["project_desc"] = team.project.description

        # team member
        team_member = []
        for item in team.requests.all():
            resume_id = 0
            if Resume.objects.filter(user=item.user):
                resume_id = Resume.objects.filter(user=item.user).first().id
            if item.status == "A":
                team_member.append(
                    {
                        "full_name": item.user.full_name,
                        "resume_id": str(resume_id),
                        "is_team_creator": True if item.user_role == "C" else False,
                        "avatar": item.user.avatar.url if item.user.avatar else None,
                    }
                )

        # set members to final data
        final_data["members"] = team_member

        return Response(final_data, status=status.HTTP_200_OK)


class UserInSameProjectAV(APIView):
    schema = TaggedAutoSchema(tags=["Team"])
    serializer_class = team.UserInfoSerializer
    permission_classes = [IsSysgod]

    def get(self, request, *args, **kwargs):
        """Get project id and returns the list of users in this project."""

        _project = get_object_or_404(models.Project, id=self.kwargs["id"])
        queryset = get_user_model().objects.filter(project__project=_project)
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminTeamCreationVS(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Team"])
    queryset = models.Team.objects.all().prefetch_related("requests")
    serializer_class = team.AdminTeamCreateSerializer
    permission_classes = [IsSysgod]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["kwargs"] = self.kwargs
        return context
