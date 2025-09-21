from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.account.models import DirectMessage

User = get_user_model()

class SendMessageInSer(serializers.Serializer):
    to = serializers.UUIDField()
    body = serializers.CharField(max_length=4000)

    def validate_to(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("کاربر مقصد یافت نشد.")
        return value

class DirectMessageOutSer(serializers.ModelSerializer):
    sender = serializers.UUIDField(source="sender_id", read_only=True)
    receiver = serializers.UUIDField(source="receiver_id", read_only=True)

    class Meta:
        model = DirectMessage
        fields = ["id", "sender", "receiver", "body", "is_read", "created_at"]


class PeerBriefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField(allow_null=True)
    avatar = serializers.CharField(allow_null=True)


class ChatThreadOutSer(serializers.Serializer):
    peer = PeerBriefSerializer()
    total_messages = serializers.IntegerField()
    unread = serializers.IntegerField()
    last_message = DirectMessageOutSer()
    messages = DirectMessageOutSer(many=True)

class ChatListItemSer(serializers.Serializer):
    peer = serializers.DictField()          # {id, full_name, avatar}
    last_message = DirectMessageOutSer()
    unread_count = serializers.IntegerField()

class ConversationMessageSer(DirectMessageOutSer):
    """
    Adds a chat-friendly direction flag:
      - 'sent'     => message.sender == request.user
      - 'received' => message.receiver == request.user
    """
    direction = serializers.SerializerMethodField()

    class Meta(DirectMessageOutSer.Meta):
        # keep original DM fields and append 'direction'
        fields = DirectMessageOutSer.Meta.fields + ["direction"]

    def get_direction(self, obj: DirectMessage) -> str:
        req = self.context.get("request")
        me_id = getattr(getattr(req, "user", None), "id", None)
        return "sent" if obj.sender_id == me_id else "received"
    

class ConversationMessageMiniSer(serializers.ModelSerializer):
    direction = serializers.SerializerMethodField()

    class Meta:
        model = DirectMessage
        fields = ["body", "is_read", "created_at", "direction"]

    def get_direction(self, obj: DirectMessage) -> str:
        viewer_id = self.context.get("viewer_id")
        return "sent" if obj.sender_id == viewer_id else "received"
