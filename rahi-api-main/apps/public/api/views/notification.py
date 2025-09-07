from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.public import models
from apps.public.api.serializers import notification

from apps.api.schema import TaggedAutoSchema

class NotificationViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Notification"])
    serializer_class = notification.NotificationSerializer
    queryset = models.Notification.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]
    ordering_fields = "__all__"
