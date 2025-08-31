# apps/account/api/serializers/connection.py
from rest_framework import serializers
from apps.account.models import Connection

class ConnectionCreateSerializer(serializers.Serializer):
    """DTO ورودی برای ارسال درخواست"""
    to_user = serializers.IntegerField(required=True)

class ConnectionSerializer(serializers.ModelSerializer):
    """DTO خروجی برای نمایش Connection"""
    class Meta:
        model = Connection
        fields = ["id", "from_user", "to_user", "status", "created_at", "updated_at"]
        read_only_fields = fields

class ConnectionDecisionSerializer(serializers.Serializer):
    """DTO ورودی برای تصمیم‌گیری"""
    decision = serializers.ChoiceField(choices=["accepted", "rejected"])
