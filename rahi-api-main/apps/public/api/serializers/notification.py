from rest_framework.serializers import Serializer, ModelSerializer, ListField, UUIDField
from apps.public.models import UserNotification

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


class UserNotificationSer(ModelSerializer):
    class Meta:
        model = UserNotification
        fields = ["id", "title", "body", "kind", "payload", "url", "is_read", "created_at"]
        read_only_fields = fields


class MarkReadSer(Serializer):
    ids = ListField(child=UUIDField(), allow_empty=False)