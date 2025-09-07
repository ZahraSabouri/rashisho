from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import SettingsPermission
from apps.settings.api.serializers.connection import ConnectionWaySerializer
from apps.settings.models import ConnectionWay
from apps.api.schema import TaggedAutoSchema


class ConnectionWayViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Settings Connection Way"])
    serializer_class = ConnectionWaySerializer
    queryset = ConnectionWay.objects.all()
    permission_classes = [SettingsPermission]
