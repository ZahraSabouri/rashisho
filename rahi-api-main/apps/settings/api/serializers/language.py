from rest_framework import serializers

from apps.settings import models


class ForeignLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ForeignLanguage
        exclude = ["deleted", "deleted_at"]
