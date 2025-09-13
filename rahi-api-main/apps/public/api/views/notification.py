from datetime import timedelta
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

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

class NotificationViewSet(viewsets.ModelViewSet):
    schema = TaggedAutoSchema(tags=["Notification"])
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]
    ordering_fields = "__all__"

    @extend_schema(
        description="Return the single active announcement for the current user context. "
                    "If user has already acknowledged or is snoozed, returns 204.",
        responses={200: AnnouncementOutSerializer, 204: OpenApiResponse(response=None)},
    )
    @action(methods=["get"], detail=False, url_path="active", permission_classes=[permissions.AllowAny])
    def active(self, request):
        notif = Notification.objects.filter(is_active=True).order_by("-created_at").first()
        if not notif:
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Anonymous users never have receipts – always show the active one
        if not request.user.is_authenticated:
            data = AnnouncementOutSerializer({"user_state": {"acknowledged": False, "snoozed_until": None}, **NotificationSerializer(notif).data}).data
            return Response(data, status=status.HTTP_200_OK)

        receipt, _ = NotificationReceipt.objects.get_or_create(notification=notif, user=request.user)
        if receipt.is_suppressed_now():
            return Response(status=status.HTTP_204_NO_CONTENT)

        payload = AnnouncementOutSerializer({
            **NotificationSerializer(notif).data,
            "user_state": {
                "acknowledged": bool(receipt.acknowledged_at),
                "snoozed_until": receipt.snoozed_until,
            },
        }).data
        return Response(payload, status=status.HTTP_200_OK)

    @extend_schema(
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
    schema = TaggedAutoSchema(tags=["Notification"])
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserNotificationSer

    def get_queryset(self):
        return UserNotification.objects.filter(user=self.request.user)

    @extend_schema(request=MarkReadSer, responses={200: OpenApiResponse(response=None)})
    @action(methods=["post"], detail=False, url_path="mark-read")
    def mark_read(self, request):
        ser = MarkReadSer(data=request.data)
        ser.is_valid(raise_exception=True)
        UserNotification.objects.filter(user=request.user, id__in=ser.validated_data["ids"]).update(is_read=True)
        return Response(status=status.HTTP_200_OK)

    @extend_schema(responses={200: OpenApiResponse(response=None)})
    @action(methods=["get"], detail=False, url_path="unread-count")
    def unread_count(self, request):
        return Response({"count": self.get_queryset().filter(is_read=False).count()}, status=status.HTTP_200_OK)
