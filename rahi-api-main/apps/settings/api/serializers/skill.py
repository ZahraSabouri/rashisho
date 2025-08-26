from rest_framework import serializers

from apps.settings import models


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Skill
        exclude = ["deleted", "deleted_at"]
