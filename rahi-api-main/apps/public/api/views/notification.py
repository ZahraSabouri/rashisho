from datetime import timedelta
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.api.schema import TaggedAutoSchema
from apps.public.models import UserNotification
from apps.public.api.serializers.notification import UserNotificationOutSer, NotificationAckInSer
from apps.api.pagination import Pagination

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.api.schema import TaggedAutoSchema
from apps.public.models import Notification, UserNotification, NotificationReceipt
from apps.public.api.serializers.notification import (
    NotificationSerializer,
    AnnouncementOutSerializer,
    UserNotificationSer,
    MarkReadSer,
    SnoozeSer,
)
from apps.public.api.serializers.notification import AnnouncementOutSerializer
from apps.public.api.serializers.notification import NotificationOutSer, NotificationMarkReadInSer


class NotificationViewSet(viewsets.ModelViewSet):
    schema = TaggedAutoSchema(tags=["Notification"])
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]
    ordering_fields = "__all__"

    @extend_schema(
        tags=["Notification"],
        description="Return the single active announcement for the current user context. "
                    "If user has already acknowledged or is snoozed, returns 204.",
        responses={200: AnnouncementOutSerializer, 204: OpenApiResponse(response=None)},
    )
    
    @action(methods=["get"], detail=False, url_path="active", permission_classes=[permissions.AllowAny])
    def active(self, request):
        notif = Notification.objects.filter(is_active=True).order_by("-created_at").first()
        if not notif:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if request.user.is_authenticated:
            receipt, _ = NotificationReceipt.objects.get_or_create(notification=notif, user=request.user)
            if receipt.is_suppressed_now():
                return Response(status=status.HTTP_204_NO_CONTENT)

        ser = AnnouncementOutSerializer(notif, context={"request": request})
        return Response(ser.data, status=status.HTTP_200_OK)


    @extend_schema(
        tags=["Notification"],
        description='Mark the given announcement as "Got it" for the current user.',
        responses={200: OpenApiResponse(response=None)},
    )
    @action(methods=["post"], detail=True, url_path="ack", permission_classes=[permissions.IsAuthenticated])
    def ack(self, request, pk=None):
        notif = self.get_object()
        receipt, _ = NotificationReceipt.objects.get_or_create(notification=notif, user=request.user)
        receipt.acknowledged_at = timezone.now()
        receipt.snoozed_until = None
        receipt.save(update_fields=["acknowledged_at", "snoozed_until"])
        return Response(status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Notification"],
        request=SnoozeSer,
        description='Snooze the announcement (e.g., "Remind later").',
        responses={200: OpenApiResponse(response=None)},
    )
    @action(methods=["post"], detail=True, url_path="snooze", permission_classes=[permissions.IsAuthenticated])
    def snooze(self, request, pk=None):
        notif = self.get_object()
        ser = SnoozeSer(data=request.data)
        ser.is_valid(raise_exception=True)
        minutes = ser.validated_data["minutes"]
        receipt, _ = NotificationReceipt.objects.get_or_create(notification=notif, user=request.user)
        receipt.snoozed_until = timezone.now() + timedelta(minutes=minutes)
        receipt.save(update_fields=["snoozed_until"])
        return Response(status=status.HTTP_200_OK)


class UserNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserNotification.objects.all()
    serializer_class = UserNotificationSer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserNotification.objects.filter(user=self.request.user)

    @action(methods=["post"], detail=False, url_path="mark-read")
    def mark_read(self, request):
        ser = MarkReadSer(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = ser.validated_data["ids"]
        (self.get_queryset().filter(id__in=ids)
             .update(is_read=True))
        return Response(status=status.HTTP_200_OK)
    
    def list(self, request, *args, **kwargs):
        qs = request.user.notifications.all().order_by("-created_at")

        is_read_param = request.query_params.get("is_read")
        if is_read_param is not None:

            truthy = {"1", "true", "t", "yes", "y"}
            falsy  = {"0", "false", "f", "no", "n"}
            val = is_read_param.strip().lower()
            if val in truthy:
                qs = qs.filter(is_read=True)
            elif val in falsy:
                qs = qs.filter(is_read=False)

        ser = UserNotificationSer(qs, many=True, context={"request": request})
        return Response(ser.data, status=status.HTTP_200_OK)


class MyNotificationsAV(APIView):
    permission_classes = [IsAuthenticated]
    schema = TaggedAutoSchema(tags=["Notifications"])

    def get(self, request):
        """
        Query params:
          - unread: bool (optional) => filter unread only
          - limit: int (default 50)
        """
        unread = (request.query_params.get("unread") or "").lower() == "true"
        try:
            limit = int(request.query_params.get("limit") or 50)
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))

        qs = (UserNotification.objects
              .filter(user=request.user)
              .order_by("-created_at"))
        if unread:
            qs = qs.filter(read_at__isnull=True)
        qs = qs[:limit]
        return Response(UserNotificationOutSer(qs, many=True).data, status=status.HTTP_200_OK)


class NotificationAckAV(APIView):
    permission_classes = [IsAuthenticated]
    schema = TaggedAutoSchema(tags=["Notifications"])

    def post(self, request, id):
        notif = get_object_or_404(UserNotification, id=id, user=request.user)
        ser = NotificationAckInSer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.apply(notif)
        return Response(UserNotificationOutSer(notif).data, status=status.HTTP_200_OK)


class NotificationListAV(APIView):
    schema = TaggedAutoSchema(tags=["Notifications"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="unread", type=bool, required=False, description="فقط نخوانده‌ها"),
            OpenApiParameter(name="page", type=int, required=False),
            OpenApiParameter(name="page_size", type=int, required=False),
        ],
        responses={200: NotificationOutSer(many=True)},
    )
    def get(self, request):
        unread = str(request.query_params.get("unread", "")).lower() in ("1", "true", "t", "yes")
        qs = UserNotification.objects.filter(user=request.user).order_by("-created_at")
        if unread:
            qs = qs.filter(is_read=False)
        paginator = Pagination()
        page = paginator.paginate_queryset(qs, request)
        data = NotificationOutSer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)

class NotificationUnreadCountAV(APIView):
    schema = TaggedAutoSchema(tags=["Notifications"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: {"type": "object", "properties": {"unread": {"type": "integer"}}}})
    def get(self, request):
        c = UserNotification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread": c}, status=200)

class NotificationMarkReadAV(APIView):
    schema = TaggedAutoSchema(tags=["Notifications"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=NotificationMarkReadInSer,
                   responses={200: {"type": "object", "properties": {"updated": {"type": "integer"}}}})
    def post(self, request):
        ser = NotificationMarkReadInSer(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = ser.validated_data["ids"]
        now = timezone.now()
        updated = (UserNotification.objects
                   .filter(user=request.user, id__in=ids, is_read=False)
                   .update(is_read=True, read_at=now))
        return Response({"updated": updated}, status=200)

class NotificationDeleteAV(APIView):
    schema = TaggedAutoSchema(tags=["Notifications"])
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(parameters=[OpenApiParameter(name="id", type=str, location=OpenApiParameter.PATH)])
    def delete(self, request, id):
        n = UserNotification.objects.filter(user=request.user, id=id).first()
        if not n:
            return Response(status=404)
        n.delete()
        return Response(status=204)