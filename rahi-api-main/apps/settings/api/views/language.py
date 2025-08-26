from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import SettingsPermission
from apps.settings.api.serializers.language import ForeignLanguageSerializer
from apps.settings.models import ForeignLanguage


class ForeignLanguageViewSet(ModelViewSet):
    serializer_class = ForeignLanguageSerializer
    queryset = ForeignLanguage.objects.all()
    permission_classes = [SettingsPermission]
