from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.serializers import Serializer, ModelSerializer, ListField, UUIDField

from apps.public.models import Announcement, UserNotification, AnnouncementReceipt
from typing import List, Optional

User = get_user_model()


class AnnouncementSerializer(ModelSerializer):
    target_users = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), 
        many=True, 
        required=False,
        help_text="خالی = برای همه کاربران"
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Announcement
        fields = "__all__"

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if rep.get("image"):
            rep["image"] = instance.image.url
        return rep
    
    def create(self, validated_data):
        # fallback in case ViewSet.perform_create isn't used
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data.setdefault("created_by", request.user)
        return super().create(validated_data)


class AnnouncementOutSerializer(AnnouncementSerializer):
    user_state = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta(AnnouncementSerializer.Meta):
        # fields = AnnouncementSerializer.Meta.fields + ["user_state"]
        fields = ["id", "title", "description", "image", "is_active", "target_users", 
                 "created_at", "updated_at", "user_state", "created_by"]

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

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["image"] = instance.image.url if instance.image else None   # like Project/Blog
        return rep

class SnoozeSer(Serializer):
    minutes = serializers.IntegerField(min_value=1, default=1440)  # 24h default


# ================================
# آگهی (Notifications) Serializers  
# ================================

class UserNotificationSerializer(ModelSerializer):
    target_users = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        required=False,
        write_only=True,
        help_text="خالی = برای همه کاربران"
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    # class Meta:
    #     model = UserNotification
    #     fields = ["id", "title", "body", "kind", "payload", "url", "target_users"]
    #     read_only_fields = ["id"]

    class Meta:
        model = UserNotification
        fields = "__all__"

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data.setdefault("created_by", request.user)
        return super().create(validated_data)

    def validate(self, attrs):
        # Remove target_users from attrs as it's handled in the view
        if 'target_users' in attrs:
            self.target_users = attrs.pop('target_users')
        return attrs


class UserNotificationOutSerializer(ModelSerializer):
    created_by = serializers.UUIDField(source="created_by_id", allow_null=True, read_only=True)

    class Meta:
        model = UserNotification
        fields = [
            "id", "kind", "title", "body", "url",
            "is_read", "created_at", "read_at",
            "created_by",
        ]


class UserNotificationCreateSerializer(serializers.ModelSerializer):
    """
    Application/Infrastructure: DRF Serializer (DTO) for *input*.
    - Hides `user` from the request (we set it server-side, one per target).
    - Accepts `target_users` (list of User UUIDs). Empty => all users.
    Django/DRF ↔ .NET: Serializer ~ DTO / AutoMapper profile.
    """
    target_users = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        required=False,
        write_only=True,
        help_text="خالی = برای همه کاربران"
    )

    # Make these read-only so they won't show up in the **request** schema
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    is_read = serializers.BooleanField(read_only=True)
    read_at = serializers.DateTimeField(read_only=True)
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = UserNotification
        # NOTE: no `user` in input fields
        fields = [
            "id", "title", "body", "kind", "payload", "url",
            "target_users", "is_read", "read_at", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_read", "read_at", "created_at", "updated_at", "created_by"]

    def validate(self, attrs):
        """
        We don't persist `target_users` on the model. Stash it on the serializer instance
        so the ViewSet can consume it after is_valid().
        """
        self._target_users: Optional[List[User]] = attrs.pop("target_users", None)
        return attrs



class MarkReadSer(Serializer):
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