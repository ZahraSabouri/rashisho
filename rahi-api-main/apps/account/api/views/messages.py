from django.db.models import Q, Count, Max, Case, When, F, OuterRef, Subquery
from django.contrib.auth import get_user_model
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from django.db import models

from apps.api.schema import TaggedAutoSchema
from apps.api.pagination import Pagination

from apps.account.models import DirectMessage
from apps.account.api.serializers.messages import (
    SendMessageInSer, DirectMessageOutSer, ChatThreadOutSer,
    ChatListItemSer, ConversationMessageSer, ConversationMessageMiniSer
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
            OpenApiParameter("page", int, OpenApiParameter.QUERY, required=False, description="Page number (1-based)"),
            OpenApiParameter("page_size", int, OpenApiParameter.QUERY, required=False, description="Items per page"),
        ],
        responses={200: DirectMessageOutSer(many=True)},
    )

    def get(self, request):
        peer = request.query_params.get("peer")
        if not peer:
            return Response({"detail": "پارامتر peer الزامی است."}, status=400)
        qs = (DirectMessage.objects
              .filter(Q(sender=request.user, receiver_id=peer) | Q(sender_id=peer, receiver=request.user))
              .order_by("-created_at"))

        paginator = Pagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = DirectMessageOutSer(page, many=True).data
        return paginator.get_paginated_response(data)


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
            OpenApiParameter("page", int, OpenApiParameter.QUERY, required=False, description="Page number (1-based)"),
            OpenApiParameter("page_size", int, OpenApiParameter.QUERY, required=False, description="Conversations per page"),
            OpenApiParameter("order", str, OpenApiParameter.QUERY, required=False, description="desc|asc (default desc)"),
        ],
        responses={200: ChatListItemSer(many=True)},
        # summary="List DM chats (one row per conversation; only the last message with each peer).",
        description="Like Telegram/Instagram chats screen. Uses your token; no path id.",
    )
    def get(self, request):
        me = request.user

        # Build unread-counts map (receiver==me, unread only)
        unread_rows = (DirectMessage.objects
                       .filter(receiver=me, is_read=False)
                       .values("sender_id")
                       .annotate(c=Count("id")))
        unread_by_peer = {str(r["sender_id"]): r["c"] for r in unread_rows}

        # Base messages annotated with the 'peer_id' relative to me
        base = (DirectMessage.objects
                .filter(Q(sender=me) | Q(receiver=me))
                .annotate(peer_id=Case(
                    When(sender_id=me.id, then=F("receiver_id")),
                    default=F("sender_id"),
                    output_field=models.UUIDField(),
                )))

        # For each peer, id of the latest message
        last_msg_id_sq = (DirectMessage.objects
                          .filter(Q(sender=me, receiver_id=OuterRef("peer_id")) |
                                  Q(sender_id=OuterRef("peer_id"), receiver=me))
                          .order_by("-created_at")
                          .values("id")[:1])

        # Queryset of peers ordered by last activity (drives pagination)
        peers_qs = (base.values("peer_id")
                         .annotate(last_created=Max("created_at"),
                                   last_msg_id=Subquery(last_msg_id_sq))
                         .order_by("-last_created"))

        paginator = Pagination()
        peers_page = paginator.paginate_queryset(peers_qs, request, view=self)

        # Fetch last messages just for this page
        last_ids = [p["last_msg_id"] for p in peers_page if p["last_msg_id"]]
        msgs = (DirectMessage.objects
                .filter(id__in=last_ids)
                .select_related("sender", "receiver")
                .order_by("-created_at"))

        order = (request.query_params.get("order") or "desc").lower()

        rows = []
        for m in msgs:
            # Determine counterpart (peer) relative to me
            peer = m.receiver if m.sender_id == me.id else m.sender
            avatar = None
            if getattr(peer, "avatar", None):
                try:
                    avatar = request.build_absolute_uri(peer.avatar.url)
                except Exception:
                    avatar = None
            rows.append({
                "peer": {"id": str(peer.id),
                         "full_name": getattr(peer, "full_name", peer.username),
                         "avatar": avatar},
                "last_message": DirectMessageOutSer(m).data,
                "unread_count": unread_by_peer.get(str(peer.id), 0),
            })

        if order == "asc":
            rows = list(reversed(rows))

        return paginator.get_paginated_response(ChatListItemSer(rows, many=True).data)
    
    
class ThreadAV(APIView):
    schema = TaggedAutoSchema(tags=["User DM"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["User DM"],
        parameters=[
            OpenApiParameter("peer", str, OpenApiParameter.QUERY, required=True,
                             description="UUID of the other participant"),
            OpenApiParameter("page", int, OpenApiParameter.QUERY, required=False,
                             description="Page number (1-based)"),
            OpenApiParameter("page_size", int, OpenApiParameter.QUERY, required=False,
                             description="Items per page"),
            OpenApiParameter("order", str, OpenApiParameter.QUERY, required=False,
                             description="asc | desc (default: asc, good for chat UIs)"),
        ],
        responses={200: ConversationMessageSer(many=True)},
        summary="Get a single DM thread (me <-> peer), paginated, with 'direction' flags."
    )
    def get(self, request):
        peer = request.query_params.get("peer")
        if not peer:
            return Response({"detail": "query param 'peer' is required."}, status=400)

        # Optional: validate peer exists (keeps errors cleaner for FE)
        if not User.objects.filter(id=peer, is_active=True).exists():
            return Response({"detail": "Peer not found or inactive."}, status=404)

        order = (request.query_params.get("order") or "asc").lower()
        ascending = order == "asc"

        qs = (
            DirectMessage.objects
            .filter(
                Q(sender=request.user, receiver_id=peer) |
                Q(sender_id=peer, receiver=request.user)
            )
            .order_by("created_at" if ascending else "-created_at")
        )

        paginator = Pagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = ConversationMessageSer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)
    
class ThreadsMultiAV(APIView):
    """
    GET /api/account/messages/threads/
    - Returns a paginated list of conversations (one item per peer).
    - Each item includes the peer UUID and a (limited) slice of messages with 'direction' flags.
    - If ?user=<uuid> is provided, shows conversations for that user (self or admin only).
      Otherwise, uses the authenticated user.
    """
    schema = TaggedAutoSchema(tags=["User DM"])
    permission_classes = [permissions.IsAuthenticated]

    def _is_admin(self, user) -> bool:
        # mirror existing admin checks used elsewhere in this module
        return bool(getattr(user, "role", None) == 0 or user.is_staff or user.is_superuser)

    @extend_schema(
        tags=["User DM"],
        parameters=[
            OpenApiParameter("user", str, OpenApiParameter.QUERY, required=False,
                             description="Target user UUID (optional). If omitted, uses the authenticated user."),
            OpenApiParameter("page", int, OpenApiParameter.QUERY, required=False,
                             description="Page number (1-based) over peers"),
            OpenApiParameter("page_size", int, OpenApiParameter.QUERY, required=False,
                             description="Number of peers (conversations) per page"),
            OpenApiParameter("per_peer_limit", int, OpenApiParameter.QUERY, required=False,
                             description="Number of messages returned per conversation (default 30, max 100)"),
            OpenApiParameter("order", str, OpenApiParameter.QUERY, required=False,
                             description="Message order inside each conversation: asc | desc (default asc)"),
        ],
        description="Telegram-like conversations page. Returns conversations grouped by peer with a small message slice.",
    )
    def get(self, request):
        # 1) resolve target user
        target_id = request.query_params.get("user") or str(request.user.id)
        target = User.objects.filter(id=target_id, is_active=True).first()
        if not target:
            return Response({"detail": "کاربر هدف یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
        if target.id != request.user.id and not self._is_admin(request.user):
            return Response({"detail": "اجازه دسترسی ندارید."}, status=status.HTTP_403_FORBIDDEN)

        # 2) params
        try:
            per_peer_limit = int(request.query_params.get("per_peer_limit") or 30)
        except ValueError:
            per_peer_limit = 30
        per_peer_limit = max(1, min(per_peer_limit, 100))

        order = (request.query_params.get("order") or "asc").lower()
        ascending = order == "asc"

        # 3) peers ordered by last activity (same pattern as ChatsAV)
        me_qs = (DirectMessage.objects
                 .filter(Q(sender_id=target.id) | Q(receiver_id=target.id))
                 .annotate(peer_id=Case(
                     When(sender_id=target.id, then=F("receiver_id")),
                     default=F("sender_id"),
                     output_field=models.UUIDField(),
                 )))

        last_msg_id_sq = (DirectMessage.objects
                          .filter(Q(sender_id=target.id, receiver_id=OuterRef("peer_id")) |
                                  Q(sender_id=OuterRef("peer_id"), receiver_id=target.id))
                          .order_by("-created_at")
                          .values("id")[:1])

        peers_qs = (me_qs.values("peer_id")
                        .annotate(last_created=Max("created_at"),
                                  last_msg_id=Subquery(last_msg_id_sq))
                        .order_by("-last_created"))

        paginator = Pagination()
        peers_page = paginator.paginate_queryset(peers_qs, request, view=self)

        # 4) build results per peer
        results = []
        for row in peers_page:
            peer_uuid = row["peer_id"]

            # slice of messages between target and this peer
            m_qs = (DirectMessage.objects
                    .filter(Q(sender_id=target.id, receiver_id=peer_uuid) |
                            Q(sender_id=peer_uuid, receiver_id=target.id))
                    .order_by("created_at" if ascending else "-created_at")[:per_peer_limit])

            # use our minimal serializer with viewer_id for correct direction
            chats = ConversationMessageMiniSer(
                m_qs, many=True, context={"viewer_id": target.id}
            ).data

            results.append({
                "peer_uuid": str(peer_uuid),
                "chats": chats,
            })

        return paginator.get_paginated_response(results)