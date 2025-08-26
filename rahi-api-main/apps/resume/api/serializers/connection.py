from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.common.serializers import CustomSlugRelatedField
from apps.resume import models
from apps.settings.models import ConnectionWay


class ConnectionSerializer(serializers.ModelSerializer):
    title = CustomSlugRelatedField(slug_field="title", queryset=ConnectionWay.objects.all())

    class Meta:
        model = models.Connection
        exclude = ["deleted_at", "deleted", "created_at", "updated_at", "resume"]

    def create(self, validated_data):
        resume = self.context.get("resume")
        step_name = "connection_ways"
        if resume:
            validated_data["resume"] = resume
            resume.finish_sub_step(step_name)
            return super().create(validated_data)
        else:
            raise ValidationError("رزومه یافت نشد!")
