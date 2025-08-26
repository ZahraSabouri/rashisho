from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.resume import models


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Project
        exclude = ["deleted_at", "deleted", "created_at", "updated_at", "resume"]

    # def validate(self, attrs):
    #     start_date = attrs.get("start_date", None)
    #     end_date = attrs.get("end_date", None)
    #     if start_date and end_date and end_date <= start_date:
    #         raise ValidationError("تاریخ پایان پروژه نمی تواند بعد از تاریخ شروع و یا همزمان با آن باشد!")
    #
    #     return super().validate(attrs)

    def create(self, validated_data):
        step_name = "project"
        resume = self.context.get("resume")
        if resume:
            validated_data["resume"] = resume
            resume.finish_sub_step(step_name)
            certificate = super().create(validated_data)
            return certificate
        else:
            raise ValidationError("رزومه یافت نشد!")
