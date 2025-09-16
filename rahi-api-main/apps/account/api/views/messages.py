from django.db.models import Q, Count, Max, Case, When, F, OuterRef, Subquery
from django.contrib.auth import get_user_model
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from apps.api.schema import TaggedAutoSchema

from apps.account.models import DirectMessage
from apps.account.api.serializers.messages import (
    SendMessageInSer, DirectMessageOutSer, ChatThreadOutSer,
    ChatListItemSer
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


class ChatsAV(APIView):
    schema = TaggedAutoSchema(tags=["User DM"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["User DM"],
        parameters=[
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False,
                             description="Max conversations to return (default 50, max 200)"),
            OpenApiParameter("order", str, OpenApiParameter.QUERY, required=False,
                             description="Message order inside each conversation: desc|asc (default desc)"),
        ],
        responses={200: ChatListItemSer(many=True)},
        # summary="List DM chats (one row per conversation; only the last message with each peer).",
        description="Like Telegram/Instagram chats screen. Uses your token; no path id.",
    )
    def get(self, request):
        me = request.user

        # Limit handling (keep fast & predictable)
        try:
            limit = int(request.query_params.get("limit") or 50)
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))

        # Compute unread counts per peer for 'me' (receiver=me, unread only)
        unread_rows = (
            DirectMessage.objects
            .filter(receiver=me, is_read=False)
            .values("sender_id")
            .annotate(c=Count("id"))
        )
        unread_by_peer = {str(r["sender_id"]): r["c"] for r in unread_rows}

        # Build a "peer_id" for each message relative to me
        base = (
            DirectMessage.objects
            .filter(Q(sender=me) | Q(receiver=me))
            .annotate(peer_id=Case(
                When(sender_id=me.id, then=F("receiver_id")),
                default=F("sender_id"),
                output_field=models.UUIDField(),
            ))
        )

        # For each peer, find the id of the latest message (subquery)
        last_msg_id_sq = (
            DirectMessage.objects
            .filter(
                Q(sender=me, receiver_id=OuterRef("peer_id")) |
                Q(sender_id=OuterRef("peer_id"), receiver=me)
            )
            .order_by("-created_at")
            .values("id")[:1]
        )

        # Get the peers ordered by last message time (desc)
        peers = (
            base.values("peer_id")
            .annotate(last_created=Max("created_at"),
                      last_msg_id=Subquery(last_msg_id_sq))
            .order_by("-last_created")[:limit]
        )

        # Fetch the last message rows in one query
        last_ids = [p["last_msg_id"] for p in peers if p["last_msg_id"]]
        msgs = (
            DirectMessage.objects
            .filter(id__in=last_ids)
            .select_related("sender", "receiver")
            .order_by("-created_at")
        )

        # Build response rows
        order = (request.query_params.get("order") or "desc").lower()
        out = []
        for m in msgs:
            # Determine the counterpart (peer) relative to me
            peer = m.receiver if m.sender_id == me.id else m.sender
            # avatar absolute URL if available
            avatar = None
            if getattr(peer, "avatar", None):
                try:
                    avatar = request.build_absolute_uri(peer.avatar.url)
                except Exception:
                    avatar = None
            out.append({
                "peer": {"id": str(peer.id), "full_name": getattr(peer, "full_name", peer.username), "avatar": avatar},
                "last_message": DirectMessageOutSer(m).data,
                "unread_count": unread_by_peer.get(str(peer.id), 0),
            })

        # Keep chats in descending recency by default; allow asc if requested
        if order == "asc":
            out = list(reversed(out))

        return Response(ChatListItemSer(out, many=True).data, status=status.HTTP_200_OK)