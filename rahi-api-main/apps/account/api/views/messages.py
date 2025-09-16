from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from apps.api.schema import TaggedAutoSchema

from apps.account.models import DirectMessage
from apps.account.api.serializers.messages import (
    SendMessageInSer, DirectMessageOutSer, ChatThreadOutSer
)

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


class UserChatsAV(APIView):
    schema = TaggedAutoSchema(tags=["User DM"])
    permission_classes = [permissions.IsAuthenticated]

    def _is_admin(self, user) -> bool:
        # keep aligned with how you detect admin elsewhere (role==0 or staff/superuser)
        return bool(getattr(user, "role", None) == 0 or user.is_staff or user.is_superuser)

    @extend_schema(
        tags=["User DM"],
        parameters=[
            OpenApiParameter("id", str, OpenApiParameter.PATH, description="UUID کاربر هدف"),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False,
                             description="حداکثر تعداد پیام در هر گفتگو (پیش‌فرض 50، حداکثر 200)"),
            OpenApiParameter("order", str, OpenApiParameter.QUERY, required=False,
                             description="ترتیب پیام‌ها در هر گفتگو: desc|asc (پیش‌فرض desc)"),
        ],
        responses={200: ChatThreadOutSer(many=True)},
        summary="فهرست همه گفتگوهای DM یک کاربر (گروه‌بندی‌شده بر اساس طرف مقابل)",
        description="برای پشتیبانی/ادمین یا خود فرد: تمامی چت‌های کاربر هدف به‌همراه آخرین پیام، تعداد خوانده‌نشده و برشی از پیام‌ها.",
    )
    def get(self, request, id):
        # authz: self or admin
        target = User.objects.filter(id=id, is_active=True).first()
        if not target:
            return Response({"detail": "کاربر یافت نشد."}, status=404)
        if request.user.id != target.id and not self._is_admin(request.user):
            return Response({"detail": "اجازه دسترسی ندارید."}, status=403)

        # query params
        try:
            limit = int(request.query_params.get("limit") or 50)
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))
        order = (request.query_params.get("order") or "desc").lower()
        asc = order == "asc"

        # collect peer ids for this user
        base = DirectMessage.objects.filter(Q(sender_id=id) | Q(receiver_id=id))
        # sets in Python are OK (keeps code simple & minimal)
        peer_ids = set(base.values_list("sender_id", flat=True)) | set(base.values_list("receiver_id", flat=True))
        peer_ids.discard(target.id)
        if not peer_ids:
            return Response([])

        # fetch peers once
        peers = {u.id: u for u in User.objects.filter(id__in=peer_ids)}

        threads = []
        for peer_id in peer_ids:
            peer = peers.get(peer_id)
            # messages between target and this peer
            m_qs = DirectMessage.objects.filter(
                Q(sender_id=id, receiver_id=peer_id) | Q(sender_id=peer_id, receiver_id=id)
            ).order_by("created_at" if asc else "-created_at")

            total = m_qs.count()
            slice_qs = list(m_qs[:limit])
            last_msg = slice_qs[-1] if asc and slice_qs else (slice_qs[0] if slice_qs else None)

            unread = DirectMessage.objects.filter(
                receiver_id=id, sender_id=peer_id, is_read=False
            ).count()

            # build peer brief (avatar may be None)
            avatar_url = None
            if peer and getattr(peer, "avatar", None):
                try:
                    avatar_url = request.build_absolute_uri(peer.avatar.url)
                except Exception:
                    avatar_url = None

            threads.append({
                "peer": {
                    "id": str(peer_id),
                    "full_name": getattr(peer, "full_name", None) if peer else None,
                    "avatar": avatar_url,
                },
                "total_messages": total,
                "unread": unread,
                "last_message": DirectMessageOutSer(last_msg).data if last_msg else None,
                "messages": DirectMessageOutSer(slice_qs, many=True).data,
            })

        # sort threads by last_message.created_at (desc) to mimic inbox ordering
        threads.sort(
            key=lambda t: (t["last_message"]["created_at"] if t["last_message"] else ""),
            reverse=True,
        )
        return Response(threads, status=200)
