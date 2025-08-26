from datetime import datetime

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.resume import models


class WorkExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.WorkExperience
        exclude = ["deleted_at", "deleted", "created_at", "updated_at", "resume"]

    def validate_end_date(self, value):
        if isinstance(self.initial_data, dict):
            start_date = datetime.strptime(self.initial_data["start_date"], "%Y-%m-%d").date()
            if value and value < start_date:
                raise ValidationError("تاریخ پایان نمی تواند قبل از تاریخ شروع باشد")
        return value

    def create(self, validated_data):
        resume = self.context.get("resume")
        if resume:
            validated_data["resume"] = resume
            resume.next_step(3)
            return super().create(validated_data)
        else:
            raise ValidationError("رزومه یافت نشد!")
