from datetime import datetime

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.common.serializers import CustomSlugRelatedField
from apps.resume import models
from apps.settings.models import StudyField, University


class EducationSerializer(serializers.ModelSerializer):
    university = CustomSlugRelatedField(slug_field="title", queryset=University.objects.all())
    field = CustomSlugRelatedField(slug_field="title", queryset=StudyField.objects.all())

    class Meta:
        model = models.Education
        exclude = ["deleted_at", "deleted", "created_at", "updated_at", "resume"]

    def validate_end_date(self, value):
        if isinstance(self.initial_data, dict):
            start_date = datetime.strptime(self.initial_data["start_date"], "%Y-%m-%d").date()
            if value and value < start_date:
                raise ValidationError("تاریخ پایان نمی تواند قبل از تاریخ شروع باشد")
        return value

    def validate_start_date(self, value):
        if isinstance(self.initial_data, dict):
            end_date_str = self.initial_data.get("end_date")
            if end_date_str is None:
                end_date = datetime.today().date()
                if value and value == end_date:
                    raise ValidationError("تاریخ شروع و پایان نمی توانند یکی باشند")
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                if value and value == end_date:
                    raise ValidationError("تاریخ شروع و پایان نمی توانند یکی باشند")
        today = datetime.today().date()
        if value and value > today:
            raise ValidationError("تاریخ شروع نمی‌تواند بعد از تاریخ امروز باشد")
        return value

    def create(self, validated_data):
        step_number = 2
        resume: models.Resume = self.context.get("resume")
        validated_data["resume"] = resume
        resume.next_step(step_number)
        return super().create(validated_data)
