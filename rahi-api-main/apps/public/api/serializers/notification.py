from rest_framework.serializers import ModelSerializer

from apps.public import models


class NotificationSerializer(ModelSerializer):
    class Meta:
        model = models.Notification
        fields = "__all__"

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if rep["image"]:
            rep["image"] = instance.image.url
        return rep
