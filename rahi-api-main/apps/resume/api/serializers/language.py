from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.common.serializers import CustomSlugRelatedField
from apps.resume import models
from apps.settings.models import ForeignLanguage


class LanguageSerializer(serializers.ModelSerializer):
    language_name = CustomSlugRelatedField(slug_field="title", queryset=ForeignLanguage.objects.all())

    class Meta:
        model = models.Language
        exclude = ["deleted_at", "deleted", "created_at", "updated_at", "resume"]

    def create(self, validated_data):
        step_name = "language"
        resume = self.context.get("resume")
        if resume:
            validated_data["resume"] = resume
            resume.finish_sub_step(step_name)
            certificate = super().create(validated_data)
            return certificate
        else:
            raise ValidationError("رزومه یافت نشد!")
