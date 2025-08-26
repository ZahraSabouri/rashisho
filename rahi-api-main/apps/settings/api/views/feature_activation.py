from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.settings.api.serializers.feature_activation import FeatureActivationSerializer
from apps.settings.models import FeatureActivation


class FeatureActivationVS(ModelViewSet):
    serializer_class = FeatureActivationSerializer
    queryset = FeatureActivation.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]
    filterset_fields = ["feature"]
