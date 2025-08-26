from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.resume import models


class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Certificate
        exclude = ["deleted_at", "deleted", "created_at", "updated_at", "resume"]

    def create(self, validated_data):
        step_name = "certification"
        resume = self.context.get("resume")
        if resume:
            validated_data["resume"] = resume
            resume.finish_sub_step(step_name)
            certificate = super().create(validated_data)
            return certificate
        else:
            raise ValidationError("رزومه یافت نشد!")
