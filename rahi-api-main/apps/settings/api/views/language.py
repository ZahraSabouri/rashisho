from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import SettingsPermission
from apps.settings.api.serializers.language import ForeignLanguageSerializer
from apps.settings.models import ForeignLanguage
from apps.api.schema import TaggedAutoSchema


class ForeignLanguageViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Settings Foreign Language"])
    serializer_class = ForeignLanguageSerializer
    queryset = ForeignLanguage.objects.all()
    permission_classes = [SettingsPermission]
