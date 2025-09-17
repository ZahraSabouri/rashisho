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
    user_state = serializers.SerializerMethodField(read_only=True)

    class Meta(NotificationSerializer.Meta):
        fields = NotificationSerializer.Meta.fields
        # fields = list(NotificationSerializer.Meta.fields) + ["user_state"]

    def get_user_state(self, obj):
        request = self.context.get("request") if hasattr(self, "context") else None
        user = getattr(request, "user", None)
        state = {"acknowledged": False, "snoozed_until": None}

        if not user or not getattr(user, "is_authenticated", False):
            return state

        receipt = NotificationReceipt.objects.filter(
            notification=obj, user=user
        ).only("acknowledged_at", "snoozed_until").first()

        if receipt:
            state["acknowledged"] = bool(receipt.acknowledged_at)
            state["snoozed_until"] = receipt.snoozed_until
        return state


class UserNotificationSer(ModelSerializer):
    class Meta:
        model = UserNotification
        fields = ["id", "title", "body", "kind", "payload", "url", "is_read", "created_at"]
        read_only_fields = fields


class MarkReadSer(Serializer):
    ids = ListField(child=UUIDField(), allow_empty=False)


class SnoozeSer(Serializer):
    minutes = serializers.IntegerField(min_value=1, default=1440)  # 24h default


class UserNotificationOutSer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = ["id", "kind", "title", "body", "url", "created_at", "read_at"]
        read_only_fields = fields

        
class NotificationOutSer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = ["id", "kind", "title", "body", "url", "is_read", "created_at", "read_at"]
        read_only_fields = fields


class NotificationMarkReadInSer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=200)


class NotificationAckInSer(serializers.Serializer):
    """
    action:
      - got_it          => mark read (do not show again)
      - remind_later    => keep unread (shows on next login)
    """
    action = serializers.ChoiceField(choices=["got_it", "remind_later"])

    def apply(self, notif: UserNotification):
        act = self.validated_data["action"]
        if act == "got_it":
            notif.read_at = timezone.now()
            notif.save(update_fields=["read_at", "updated_at"])
        # remind_later: do nothing (still unread)
        return notif
