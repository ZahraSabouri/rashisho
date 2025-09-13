from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import Serializer, ModelSerializer, ListField, UUIDField

from apps.public import models
from apps.public.models import UserNotification, NotificationReceipt

class NotificationSerializer(ModelSerializer):
    class Meta:
        model = models.Notification
        fields = "__all__"

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if rep.get("image"):
            rep["image"] = instance.image.url
        return rep


class AnnouncementStateSerializer(Serializer):
    """State of current user for the given announcement."""
    acknowledged = serializers.BooleanField()
    snoozed_until = serializers.DateTimeField(allow_null=True)


class AnnouncementOutSerializer(NotificationSerializer):
    """Notification + current user's state (for /active endpoint)."""
    user_state = AnnouncementStateSerializer()

    class Meta(NotificationSerializer.Meta):
        fields = list(NotificationSerializer.Meta.fields) + ["user_state"]


class UserNotificationSer(ModelSerializer):
    class Meta:
        model = UserNotification
        fields = ["id", "title", "body", "kind", "payload", "url", "is_read", "created_at"]
        read_only_fields = fields


class MarkReadSer(Serializer):
    ids = ListField(child=UUIDField(), allow_empty=False)


class SnoozeSer(Serializer):
    minutes = serializers.IntegerField(min_value=1, default=1440)  # 24h default