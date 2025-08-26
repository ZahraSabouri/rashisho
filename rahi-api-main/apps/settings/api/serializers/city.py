from rest_framework import serializers

from apps.settings import models


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.City
        fields = "__all__"
