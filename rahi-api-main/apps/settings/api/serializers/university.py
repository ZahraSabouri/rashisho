from rest_framework import serializers

from apps.settings import models


class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.University
        fields = "__all__"
