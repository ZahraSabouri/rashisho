from rest_framework.viewsets import ModelViewSet
from django_filters import rest_framework as filters

from apps.api.permissions import SettingsPermission
from apps.settings.api.serializers.university import UniversitySerializer
from apps.settings.models import University


class UniversityFilterSet(filters.FilterSet):
    title = filters.CharFilter(field_name='title', lookup_expr='icontains')
    class Meta:
        model = University
        fields = "__all__"

class UniversityViewSet(ModelViewSet):
    serializer_class = UniversitySerializer
    queryset = University.objects.all()
    permission_classes = [SettingsPermission]
    filterset_class = UniversityFilterSet
