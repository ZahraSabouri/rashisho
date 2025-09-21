from rest_framework.viewsets import ModelViewSet
from django_filters import rest_framework as filters

from apps.api.permissions import SettingsPermission
from apps.settings.api.serializers.province import ProvinceSerializer
from apps.settings.models import Province
from apps.api.schema import TaggedAutoSchema



class ProvinceFilterSet(filters.FilterSet):
    schema = TaggedAutoSchema(tags=["Settings Province"])
    title = filters.CharFilter(field_name='title', lookup_expr='icontains')
    class Meta:
        model = Province
        fields = "__all__"

class ProvinceViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Settings Province"])
    serializer_class = ProvinceSerializer
    queryset = Province.objects.all()
    permission_classes = [SettingsPermission]
    filterset_class = ProvinceFilterSet
