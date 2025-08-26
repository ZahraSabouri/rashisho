from rest_framework import serializers

from apps.settings import models


class ConnectionWaySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ConnectionWay
        exclude = ["deleted", "deleted_at"]
