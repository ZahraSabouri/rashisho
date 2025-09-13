from rest_framework import serializers
from apps.account.models import Connection


class ConnectionCreateSerializer(serializers.Serializer):
    to_user = serializers.UUIDField(required=True) 


class ConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Connection
        fields = ["id", "from_user", "to_user", "status", "created_at", "updated_at"]
        read_only_fields = fields


class ConnectionDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["accepted", "rejected"])



class PendingConnectionOutSerializer(serializers.ModelSerializer):
    peer = serializers.SerializerMethodField()

    class Meta:
        model = Connection
        # keep original fields to avoid breaking existing consumers; just add 'peer'
        fields = ["id", "from_user", "to_user", "status", "created_at", "updated_at", "peer"]
        read_only_fields = fields

    def _avatar_url(self, request, user):
        if user and getattr(user, "avatar", None):
            try:
                return request.build_absolute_uri(user.avatar.url) if request else user.avatar.url
            except Exception:
                return None
        return None

    def get_peer(self, obj):
        request = self.context.get("request")
        me = getattr(request, "user", None)
        # decide counterpart relative to the requesting user
        counterpart = obj.to_user if me and obj.from_user_id == me.id else obj.from_user
        # user_info already stores first_name/last_name; model exposes full_name/user_id properties
        return {
            "id": str(counterpart.id),
            "user_id": getattr(counterpart, "user_id", None),        # SSO id property
            "full_name": getattr(counterpart, "full_name", None),
            "first_name": counterpart.user_info.get("first_name") if getattr(counterpart, "user_info", None) else None,
            "last_name": counterpart.user_info.get("last_name") if getattr(counterpart, "user_info", None) else None,
            "avatar": self._avatar_url(request, counterpart),
        }