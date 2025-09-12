from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from apps.api.schema import TaggedAutoSchema

from apps.account.models import DirectMessage
from apps.account.api.serializers.messages import  SendMessageInSer, DirectMessageOutSer

User = get_user_model()

class SendMessageAV(APIView):
    schema = TaggedAutoSchema(tags=["User DM"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["User DM"],
        request=SendMessageInSer,
        responses={201: DirectMessageOutSer},
        summary="ارسال پیام مستقیم به یک کاربر",
        description="برای دکمه «ارسال پیام» در پروفایل. پیام ذخیره می‌شود..."
    )
    def post(self, request):
        ser = SendMessageInSer(data=request.data)
        ser.is_valid(raise_exception=True)
        to_id = ser.validated_data["to"]
        body = ser.validated_data["body"]
        msg = DirectMessage.objects.create(
            sender=request.user, receiver_id=to_id, body=body
        )
        return Response(DirectMessageOutSer(msg).data, status=status.HTTP_201_CREATED)

class ConversationListAV(APIView):
    schema = TaggedAutoSchema(tags=["User DM"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["User DM"],
        parameters=[
            OpenApiParameter("peer", str, OpenApiParameter.QUERY, required=True, description="UUID کاربر مقابل"),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False, description="پیش‌فرض 50"),
        ],
        responses={200: DirectMessageOutSer(many=True)},
    )

    def get(self, request):
        peer = request.query_params.get("peer")
        if not peer:
            return Response({"detail": "پارامتر peer الزامی است."}, status=400)
        limit = int(request.query_params.get("limit") or 50)
        qs = (DirectMessage.objects
              .filter(Q(sender=request.user, receiver_id=peer) | Q(sender_id=peer, receiver=request.user))
              .order_by("-created_at")[:limit])
        return Response(DirectMessageOutSer(qs, many=True).data)

class MarkReadAV(APIView):
    schema = TaggedAutoSchema(tags=["User DM"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["User DM"],
        parameters=[OpenApiParameter("peer", str, OpenApiParameter.QUERY, required=True, description="همه پیام‌های خوانده‌نشده از این کاربر را خوانده علامت بزن")],
        responses={200: {"type": "object", "properties": {"updated": {"type": "integer"}}}},
    )
    def post(self, request):
        peer = request.query_params.get("peer")
        if not peer:
            return Response({"detail": "پارامتر peer الزامی است."}, status=400)
        updated = (DirectMessage.objects
                   .filter(receiver=request.user, sender_id=peer, is_read=False)
                   .update(is_read=True))
        return Response({"updated": updated}, status=200)

class UnreadCountAV(APIView):
    schema = TaggedAutoSchema(tags=["User DM"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["User DM"],
        responses={200: {"type": "object", "properties": {
            "total_unread": {"type": "integer"},
            "by_peer": {"type": "object", "additionalProperties": {"type": "integer"}}
        }}},
        summary="تعداد پیام‌های خوانده‌نشده (کل و به تفکیک فرستنده)"
    )
    def get(self, request):
        total = DirectMessage.objects.filter(receiver=request.user, is_read=False).count()
        # unread per peer
        per = (DirectMessage.objects
               .filter(receiver=request.user, is_read=False)
               .values("sender_id")
               .annotate(c=Count("id")))
        by_peer = {str(r["sender_id"]): r["c"] for r in per}
        return Response({"total_unread": total, "by_peer": by_peer})
