from rest_framework.serializers import ModelSerializer

from apps.exam import models


class UserAnswer(ModelSerializer):
    class Meta:
        model = models.UserAnswer
        exclude = ["deleted", "deleted_at"]
