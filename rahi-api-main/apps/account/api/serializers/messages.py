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
