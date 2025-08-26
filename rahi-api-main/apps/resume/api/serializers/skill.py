from rest_framework import serializers

from apps.common.serializers import CustomSlugRelatedField
from apps.resume import models
from apps.settings.models import Skill


class SkillSerializer(serializers.ModelSerializer):
    skill_name = CustomSlugRelatedField(
        slug_field="title", queryset=Skill.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = models.Skill
        exclude = ["deleted_at", "deleted", "created_at", "updated_at", "resume"]

    def validate(self, attrs):
        skill = self.initial_data.get("title", None)
        if skill:
            try:
                skill_obj = Skill.objects.filter(title=skill).first()
            except Exception:
                skill_obj = None

            if skill_obj:
                attrs["skill_name"] = skill_obj
            else:
                new_skill = Skill.objects.create(title=skill)
                attrs["skill_name"] = new_skill

        return super().validate(attrs)

    def create(self, validated_data):
        resume = self.context.get("resume")
        validated_data["resume"] = resume
        resume.finish_flow()
        return super().create(validated_data)
