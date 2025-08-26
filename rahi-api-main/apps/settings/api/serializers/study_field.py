from rest_framework import serializers

from apps.settings import models


class StudyFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StudyField
        fields = "__all__"
