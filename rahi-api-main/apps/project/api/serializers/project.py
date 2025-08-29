from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.account.models import User
from apps.common.serializers import CustomSlugRelatedField
from apps.project import models
from apps.project.api.serializers import team
from apps.resume.models import Resume
from apps.settings.api.serializers.study_field import StudyFieldSerializer
from apps.project.api.serializers.tag import ProjectTagSerializer
from apps.resume.models import Resume
from apps.settings.api.serializers.study_field import StudyFieldSerializer


class ScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Scenario
        exclude = ["deleted", "deleted_at"]

    def validate(self, attrs):
        scenarios = models.Scenario.objects.filter(project=attrs.get("project"))
        for scenario in scenarios:
            if scenario.number == attrs.get("number"):
                raise ValidationError("سناریو با این شماره از قبل موجود است!")

        return super().validate(attrs)

    def create(self, validated_data):
        scenarios = models.Scenario.objects.filter(project=validated_data.get("project"))
        if scenarios.count() == 3:
            raise ValidationError("برای این پروژه 3 سناریو ثبت شده است!")

        return super().create(validated_data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["first_file"] = instance.first_file.url if instance.first_file else None
        rep["second_file"] = instance.second_file.url if instance.second_file else None
        return rep


class TaskSerializer(serializers.ModelSerializer):
    second_file = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = models.Task
        exclude = ["deleted", "deleted_at"]

    def validate(self, attrs):
        tasks = models.Task.objects.filter(project=attrs.get("project"))
        for task in tasks:
            if task.number == attrs.get("number"):
                raise ValidationError("کارویژه با این شماره از قبل موجود است!")

        return super().validate(attrs)

    def create(self, validated_data):
        tasks = models.Task.objects.filter(project=validated_data.get("project"))
        if tasks.count() == 3:
            raise ValidationError("برای این پروژه 3 کارویژه ثبت شده است!")

        return super().create(validated_data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["first_file"] = instance.first_file.url if instance.first_file else None
        return rep


class ProjectDerivativesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ProjectDerivatives
        exclude = ["deleted", "deleted_at"]

    def validate(self, attrs):
        derivatives = models.ProjectDerivatives.objects.filter(
            project=attrs.get("project"), derivatives_type=attrs.get("derivatives_type")
        )
        for d in derivatives:
            if d.number == attrs.get("number"):
                raise ValidationError(f"{derivatives.get_derivatives_type_display()} با این شماره از قبل موجود است!")

        return super().validate(attrs)

    def create(self, validated_data):
        derivatives = models.ProjectDerivatives.objects.filter(
            project=validated_data.get("project"), derivatives_type=validated_data.get("derivatives_type")
        )
        if derivatives.count() == 3:
            raise ValidationError(f"برای این پروژه 3 {derivatives.get_derivatives_type_display()} ثبت شده است!")

        return super().create(validated_data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["first_file"] = instance.first_file.url if instance.first_file else None
        return rep


class ProjectSerializer(serializers.ModelSerializer):
    project_scenario = ScenarioSerializer(many=True, read_only=True)
    project_task = TaskSerializer(many=True, read_only=True)
    study_fields = StudyFieldSerializer(many=True, read_only=True)
    tags = ProjectTagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="فهرست IDهای تگ‌هایی که می‌خواهید به پروژه اضافه کنید"
    )

    class Meta:
        model = models.Project
        exclude = ["deleted", "deleted_at"]

    def create(self, validated_data):
        # Extract tag_ids and study_fields_ids before creating project
        tag_ids = validated_data.pop('tag_ids', [])
        study_fields_ids = self.context.get('study_fields_ids', [])
        
        # Create the project
        project = super().create(validated_data)
        
        # Set study fields (your existing logic)
        if study_fields_ids:
            project.study_fields.set(study_fields_ids)
        
        # ADD THIS: Set tags
        if tag_ids:
            # Validate that all tag IDs exist
            existing_tags = models.Tag.objects.filter(id__in=tag_ids)
            if existing_tags.count() != len(tag_ids):
                # Clean up and raise error
                project.delete()
                raise ValidationError("برخی از تگ‌های انتخاب شده معتبر نیستند")
            project.tags.set(existing_tags)
        
        return project

    def update(self, instance, validated_data):
        # Extract tag_ids before updating
        tag_ids = validated_data.pop('tag_ids', None)
        study_fields_ids = self.context.get('study_fields_ids', None)
        
        # Update the project
        instance = super().update(instance, validated_data)
        
        # Update study fields if provided (your existing logic)
        if study_fields_ids is not None:
            instance.study_fields.set(study_fields_ids)
        
        # ADD THIS: Update tags if provided
        if tag_ids is not None:
            if tag_ids:
                existing_tags = models.Tag.objects.filter(id__in=tag_ids)
                if existing_tags.count() != len(tag_ids):
                    raise ValidationError("برخی از تگ‌های انتخاب شده معتبر نیستند")
                instance.tags.set(existing_tags)
            else:
                # Clear all tags if empty list provided
                instance.tags.clear()
        
        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["image"] = instance.image.url if instance.image else None
        rep["video"] = instance.video.url if instance.video else None
        rep["file"] = instance.file.url if instance.file else None
        # Include tag count for convenience
        rep["tags_count"] = instance.tags.count()
        return rep


class UserProjectSerializer(serializers.ModelSerializer):
    project_scenario = serializers.SerializerMethodField()
    project_task = serializers.SerializerMethodField()
    study_fields = StudyFieldSerializer(many=True, read_only=True)
    tags = ProjectTagSerializer(many=True, read_only=True)

    class Meta:
        model = models.Project
        exclude = ["deleted", "deleted_at"]

    def get_project_scenario(self, obj):
        user = self.context["request"].user
        user_allocate = models.ProjectAllocation.objects.filter(user=user).first()
        if user_allocate:
            user_project = user_allocate.project
            if user_project:
                scenarios = obj.project_scenario.filter(project=user_project)
                return ScenarioSerializer(scenarios, many=True).data
        return None

    def get_project_task(self, obj):
        user = self.context["request"].user
        user_allocate = models.ProjectAllocation.objects.filter(user=user).first()
        if user_allocate:
            user_project = user_allocate.project
            if user_project:
                tasks = obj.project_task.filter(project=user_project)
                return TaskSerializer(tasks, many=True).data
        return None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["image"] = instance.image.url if instance.image else None
        rep["video"] = instance.video.url if instance.video else None
        rep["file"] = instance.file.url if instance.file else None

        rep["tags_count"] = instance.tags.count()
        return rep


class ProjectListSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Project
        fields = ["id", "title"]


class ProjectPrioritySerializer(serializers.ModelSerializer):
    priority = serializers.JSONField(required=True)
    project = CustomSlugRelatedField(
        slug_field="title", queryset=models.Project.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = models.ProjectAllocation
        exclude = ["deleted", "deleted_at", "created_at", "updated_at"]
        read_only_fields = ["user"]

    def validate_priority(self, value):
        keys = set(value.keys())
        priority_keys = {"1", "2", "3", "4", "5"}
        values_list = []

        for item in value.values():
            if item is not None:
                values_list.append(item)

        for item in values_list:
            if not models.Project.objects.filter(id=item).exists():
                raise ValidationError("یک پروژه معتبر انتخاب کنید!")

        if len(set(values_list)) != len(values_list):
            raise ValidationError("هر پروژه فقط یکبار می تواند انتخاب شود!")

        for key in keys:
            if key not in priority_keys:
                raise ValidationError("فرمت دیکشنری ارسالی صحیح نمی باشد!")

        return value

    def to_representation(self, instance: models.ProjectAllocation):
        result = super().to_representation(instance)
        user: User = instance.user

        for key, value in instance.priority.items():
            if key and value:
                project = get_object_or_404(models.Project, id=value)
                result["priority"].update({f"{key}": {"id": value, "text": project.title}})

        result["user"] = {
            "full_name": user.full_name,
            "national_id": user.user_info["national_id"],
            "resume": user.resume.id if Resume.objects.filter(user=user).exists() else None,
        }
        return result


class ProjectAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ProjectAllocation
        exclude = ["deleted", "deleted_at"]
        read_only_fields = ["user", "priority"]


class FinalRepresentationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FinalRepresentation
        exclude = ["deleted", "deleted_at"]
        read_only_fields = ["user", "project"]

    def validate(self, attrs):
        _user = self.context["request"].user
        user_request = models.TeamRequest.objects.filter(user=_user, user_role="C", status="A").first()
        if not user_request:
            raise ValidationError("فقط سر تیم می تواند فایل ارائه نهایی را ارسال کند!")

        user_team = models.Team.objects.get(id=user_request.team.id)

        if user_team.project != self.context["allocated_project"]:
            raise ValidationError("پروژه تخصیص داده شده به شما با پروژه تیم شما مغایرت دارد!")

        return super().validate(attrs)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["file"] = instance.file.url
        return rep


class AdminFinalRepSerializer(serializers.ModelSerializer):
    project = ProjectSerializer()
    user = CustomSlugRelatedField(slug_field="full_name", queryset=User.objects.all())

    class Meta:
        model = models.FinalRepresentation
        exclude = ["deleted", "deleted_at", "created_at", "updated_at"]
        read_only_fields = ["user", "project"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        user_team = models.TeamRequest.objects.filter(user=instance.user).first().team
        rep["team"] = team.TeamSerializer(user_team).data
        rep["file"] = instance.file.url
        return rep


class AdminFinalRepSerializerV2(serializers.ModelSerializer):
    user = CustomSlugRelatedField(slug_field="full_name", queryset=User.objects.all())

    class Meta:
        model = models.UserScenarioTaskFile
        exclude = ["deleted", "deleted_at", "created_at", "updated_at"]
        read_only_fields = ["user"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        user_team = models.TeamRequest.objects.filter(user=instance.user).first().team
        rep["team"] = team.TeamSerializer(user_team).data
        rep["file"] = instance.file.url
        rep["project"] = {
            "title": instance.derivatives.project.title,
            "value": instance.derivatives.project.id,
            "description": instance.derivatives.project.description,
        }
        return rep


class HomePageProjectSerializer(serializers.ModelSerializer):
    study_fields = StudyFieldSerializer(many=True, read_only=True)
    tags = ProjectTagSerializer(many=True, read_only=True)

    class Meta:
        model = models.Project
        exclude = ["deleted", "deleted_at", "created_at", "updated_at"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["image"] = instance.image.url if instance.image else None
        rep["video"] = instance.video.url if instance.video else None
        rep["file"] = instance.file.url if instance.file else None
        return rep


class ScenarioTaskSerializer(serializers.ModelSerializer):
    user = CustomSlugRelatedField(
        slug_field="full_name", queryset=get_user_model().objects.all(), required=False, allow_null=True
    )
    scenario = CustomSlugRelatedField(
        slug_field="title", queryset=models.Scenario.objects.all(), required=False, allow_null=True
    )
    task = CustomSlugRelatedField(
        slug_field="title", queryset=models.Task.objects.all(), required=False, allow_null=True
    )
    derivatives = CustomSlugRelatedField(
        slug_field="title", queryset=models.ProjectDerivatives.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = models.UserScenarioTaskFile
        exclude = ["deleted", "deleted_at"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["file"] = instance.file.url if instance.file else None
        rep["user"] = (
            [{"value": instance.user.id, "text": instance.user.full_name}]
            if self.context["request"].user == instance.user or self.context["request"].user.role == 0
            else None
        )
        return rep
