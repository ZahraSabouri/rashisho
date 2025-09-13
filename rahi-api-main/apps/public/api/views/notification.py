from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.api.permissions import IsAdminOrReadOnlyPermission

from apps.public.models import Notification, UserNotification
from apps.public.api.serializers.notification import NotificationSerializer, UserNotificationSer, MarkReadSer
from apps.api.schema import TaggedAutoSchema

from apps.api.schema import TaggedAutoSchema

class NotificationViewSet(viewsets.ModelViewSet):
    schema = TaggedAutoSchema(tags=["Notification"])
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]
    ordering_fields = "__all__"


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