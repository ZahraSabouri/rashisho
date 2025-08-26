from rest_framework.viewsets import ModelViewSet
from django_filters import rest_framework as filters

from apps.api.permissions import SettingsPermission
from apps.settings.api.serializers.city import CitySerializer
from apps.settings.models import City

class CityFilterSet(filters.FilterSet):
    title = filters.CharFilter(field_name='title', lookup_expr='icontains')
    class Meta:
        model = City
        fields = "__all__"

class CityViewSet(ModelViewSet):
    serializer_class = CitySerializer
    queryset = City.objects.all()
    permission_classes = [SettingsPermission]
    filterset_class = CityFilterSet
