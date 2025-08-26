from rest_framework import serializers

from apps.settings import models


class ProvinceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Province
        fields = "__all__"
