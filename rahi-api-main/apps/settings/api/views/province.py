from rest_framework.viewsets import ModelViewSet
from django_filters import rest_framework as filters

from apps.api.permissions import SettingsPermission
from apps.settings.api.serializers.province import ProvinceSerializer
from apps.settings.models import Province



class ProvinceFilterSet(filters.FilterSet):
    title = filters.CharFilter(field_name='title', lookup_expr='icontains')
    class Meta:
        model = Province
        fields = "__all__"

class ProvinceViewSet(ModelViewSet):
    serializer_class = ProvinceSerializer
    queryset = Province.objects.all()
    permission_classes = [SettingsPermission]
    filterset_class = ProvinceFilterSet
