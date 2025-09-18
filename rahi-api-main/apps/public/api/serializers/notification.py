from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.serializers import Serializer, ModelSerializer, ListField, UUIDField

from apps.public.models import Announcement, UserNotification, AnnouncementReceipt

User = get_user_model()


# ================================
# اعلانات (Announcements) Serializers
# ================================

class AnnouncementSerializer(ModelSerializer):
    """Serializer for اعلانات CRUD (admin use)"""
    target_users = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), 
        many=True, 
        required=False,
        help_text="خالی = برای همه کاربران"
    )

    class Meta:
        model = Announcement
        fields = "__all__"

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if rep.get("image"):
            rep["image"] = instance.image.url
        return rep


class AnnouncementOutSerializer(AnnouncementSerializer):
    """Serializer for اعلانات with user state (for /active/ endpoint)"""
    user_state = serializers.SerializerMethodField(read_only=True)

    class Meta(AnnouncementSerializer.Meta):
        # fields = AnnouncementSerializer.Meta.fields + ["user_state"]
        fields = ["id", "title", "description", "image", "is_active", "target_users", 
                 "created_at", "updated_at", "user_state"]

    def get_user_state(self, obj):
        request = self.context.get("request") if hasattr(self, "context") else None
        user = getattr(request, "user", None)
        state = {"acknowledged": False, "snoozed_until": None}

        if not user or not getattr(user, "is_authenticated", False):
            return state

        receipt = AnnouncementReceipt.objects.filter(
            announcement=obj, user=user
        ).only("acknowledged_at", "snoozed_until").first()

        if receipt:
            state["acknowledged"] = bool(receipt.acknowledged_at)
            state["snoozed_until"] = receipt.snoozed_until
        return state


class SnoozeSer(Serializer):
    """Serializer for snoozing اعلانات ("Remind later")"""
    minutes = serializers.IntegerField(min_value=1, default=1440)  # 24h default


# ================================
# آگهی (Notifications) Serializers  
# ================================

class UserNotificationSerializer(ModelSerializer):
    """Serializer for آگهی creation (admin use)"""
    target_users = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        required=False,
        write_only=True,
        help_text="خالی = برای همه کاربران"
    )

    class Meta:
        model = UserNotification
        fields = ["id", "title", "body", "kind", "payload", "url", "target_users"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        # Remove target_users from attrs as it's handled in the view
        if 'target_users' in attrs:
            self.target_users = attrs.pop('target_users')
        return attrs


class UserNotificationOutSerializer(ModelSerializer):
    """Serializer for آگهی output (user consumption)"""
    class Meta:
        model = UserNotification
        fields = ["id", "kind", "title", "body", "url", "is_read", "created_at", "read_at"]
        read_only_fields = fields


class MarkReadSer(Serializer):
    """Serializer for marking آگهی as read (batch operation)"""
    ids = ListField(child=UUIDField(), min_length=1, max_length=200)


# ================================
# Legacy/Compatibility (to be removed after refactoring)
# ================================

# Keep these temporarily to avoid breaking existing code
NotificationSerializer = AnnouncementSerializer  # DEPRECATED
AnnouncementStateSerializer = Serializer  # DEPRECATED
UserNotificationSer = UserNotificationOutSerializer  # DEPRECATED
NotificationOutSer = UserNotificationOutSerializer  # DEPRECATED
NotificationMarkReadInSer = MarkReadSer  # DEPRECATED