import datetime

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.account.models import User
from apps.common.serializers import CustomSlugRelatedField
from apps.project import models
from apps.resume.api.serializers import education, skill
from apps.resume.models import Resume


class TeamSerializer(serializers.ModelSerializer):
    teammate = serializers.SlugRelatedField(
        slug_field="user_info__id", queryset=User.objects.all(), many=True, write_only=True
    )

    class Meta:
        model = models.Team
        fields = ["id", "description", "title", "count", "project", "teammate"]
        read_only_fields = ["project"]

    def validate(self, attrs):
        user = self.context.get("request").user
        if models.TeamRequest.objects.filter(user=user, status="A").exists():
            raise ValidationError("شما عضو یک تیم هستید!")

        return super().validate(attrs)

    def create(self, validated_data):
        teammates = validated_data.pop("teammate", [])
        team = models.Team.objects.create(**validated_data)
        if teammates:
            for teammate in teammates:
                models.TeamRequest.objects.create(user=teammate, team=team, user_role="M")
        return team

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        team_requests = models.TeamRequest.objects.filter(team=instance, status="A")
        if team_requests:
            rep["members"] = []
            for team_request in team_requests:
                rep["members"].append(TeamRequestSerializer(team_request).data)
        return rep


class TeamRequestSerializer(serializers.ModelSerializer):
    team = CustomSlugRelatedField(slug_field="title", queryset=models.Team.objects.all())
    status = serializers.ChoiceField(choices=models.TeamRequest.REQUEST_STATUS)

    class Meta:
        model = models.TeamRequest
        exclude = ["deleted", "deleted_at"]
        read_only_fields = ["user", "team", "user_role", "description"]

    def validate(self, attrs):
        _user = self.context["request"].user
        request_status = attrs.get("status")
        user_request = models.TeamRequest.objects.filter(user=_user, status="A").first()
        if user_request and request_status == "A":
            raise ValidationError("شما قبلا عضو تیم دیگری شده اید!")

        return super().validate(attrs)

    def to_representation(self, instance: models.TeamRequest):
        rep = super().to_representation(instance)
        _user: User = instance.user
        rep["user_role"] = instance.get_user_role_display()
        rep["status"] = instance.get_status_display()
        rep["user"] = {
            "id": _user.id,
            "full_name": _user.full_name,
            "avatar": _user.avatar.url if _user.avatar else None,
            "email": _user.user_info.get("email", None),
            "resume": _user.resume.id if Resume.objects.filter(user=_user).exists() else None,
        }
        return rep


class TeammateInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["user_id", "full_name", "user_info", "avatar"]
        read_only_fields = ["user_id", "full_name"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        user_resume = Resume.objects.filter(user=instance).first()
        rep["user_info"] = {
            "email": instance.user_info["email"] if instance.user_info.get("email", None) else None,
            "mobile_number": instance.user_info["mobile_number"],
        }
        if user_resume:
            rep["educations"] = []
            user_educations = user_resume.educations.all()
            for user_education in user_educations:
                rep["educations"].append(education.EducationSerializer(user_education).data)

            rep["skills"] = []
            user_skills = user_resume.skills.all()
            for user_skill in user_skills:
                rep["skills"].append(skill.SkillSerializer(user_skill).data)

        return rep


class UsersTeamRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["user_id", "full_name", "avatar"]
        read_only_fields = ["user_id", "full_name"]

    def to_representation(self, instance: User):
        rep = super().to_representation(instance)
        requested_user = self.context["requested_user"]
        request = models.TeamRequest.objects.filter(user=requested_user, user_role="C").first()
        if request:
            team = request.team
            requests = models.TeamRequest.objects.filter(team=team, user=instance).first()
            rep["status"] = requests.get_status_display() if requests else None
        else:
            rep["status"] = None

        rep["resume_id"] = instance.resume.id
        rep["user_info"] = {
            "first_name": instance.user_info.get("first_name", None),
            "last_name": instance.user_info.get("last_name", None),
        }
        return rep


class AdminTeamRequestSerializer(serializers.ModelSerializer):
    user = CustomSlugRelatedField(slug_field="full_name", queryset=User.objects.all())

    class Meta:
        model = models.TeamRequest
        fields = ["user", "user_role"]


class AdminTeamCreateSerializer(serializers.ModelSerializer):
    teammates = AdminTeamRequestSerializer(write_only=True, many=True)
    requests = AdminTeamRequestSerializer(read_only=True, many=True)

    class Meta:
        model = models.Team
        fields = ["id", "description", "title", "count", "project", "teammates", "requests"]

    def validate(self, attrs):
        if len(attrs.get("teammates", None)) > attrs.get("count", None):
            raise ValidationError("تعداد اعضا مطابقت ندارد!")

        user_role_list = []
        teammates = attrs.get("teammates", None)
        for teammate in teammates:
            team_request = models.TeamRequest.objects.filter(user_id=teammate.get("user"), status="A").first()
            if teammate.get("user_role") == "C":
                user_role_list.append(teammate.get("user_role"))

            if team_request:
                if (
                    self.context.get("request").method == "PATCH"
                    and team_request.user_role == "C"
                    and not str(team_request.team.id) == self.context.get("kwargs").get("pk")
                ):
                    raise ValidationError(
                        f" {team_request.user.full_name} در تیم قبلی خود مسئول تیم است و نمیتواند از آن تیم حذف شده و به تیم جدید اضافه شود."
                    )

                if self.context.get("request").method == "POST" and team_request.user_role == "C":
                    raise ValidationError(
                        f" {team_request.user.full_name} در تیم قبلی خود مسئول تیم است و نمیتواند از آن تیم حذف شده و به تیم جدید اضافه شود."
                    )

                team_request.delete()

        if len(user_role_list) != 1:
            raise ValidationError("مسئول تیم فقط یک نفر می تواند باشد.")

        return super().validate(attrs)

    def create(self, validated_data):
        teammates = validated_data.pop("teammates", [])
        validated_data["create_date"] = datetime.datetime.now()
        team = models.Team.objects.create(**validated_data)
        if teammates:
            for teammate in teammates:
                models.TeamRequest.objects.create(
                    team=team, user=teammate["user"], user_role=teammate["user_role"], status="A"
                )
        return team

    def update(self, instance, validated_data):
        teammates = validated_data.pop("teammates", [])
        if teammates:
            models.TeamRequest.objects.filter(team=instance).delete()
            for teammate in teammates:
                models.TeamRequest.objects.create(
                    team=instance, user=teammate["user"], user_role=teammate["user_role"], status="A"
                )
        return super().update(instance, validated_data)


class UserInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "full_name", "avatar"]

    def to_representation(self, instance: User):
        team_request = models.TeamRequest.objects.filter(user=instance, status="A").first()
        rep = super().to_representation(instance)
        rep["has_team"] = {"id": team_request.team.id, "title": team_request.team.title} if team_request else None
        rep["avatar"] = instance.avatar.url if instance.avatar else None
        rep["resume_id"] = instance.resume.id if instance.resume else None
        return rep
