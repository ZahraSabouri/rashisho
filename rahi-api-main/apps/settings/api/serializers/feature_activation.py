from rest_framework import serializers

from apps.settings import models


class FeatureActivationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FeatureActivation
        exclude = ["deleted", "deleted_at"]

    def to_representation(self, instance: models.FeatureActivation):
        representation = super().to_representation(instance)
        representation["feature"] = instance.get_feature_display()
        return representation
