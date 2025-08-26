from rest_framework.viewsets import ModelViewSet
from django_filters import rest_framework as filters

from apps.api.permissions import SettingsPermission
from apps.settings.api.serializers.skill import SkillSerializer
from apps.settings.models import Skill


class SkillFilterSet(filters.FilterSet):
    title = filters.CharFilter(field_name='title', lookup_expr='icontains')
    class Meta:
        model = Skill
        fields = "__all__"

class SkillViewSet(ModelViewSet):
    serializer_class = SkillSerializer
    queryset = Skill.objects.all()
    permission_classes = [SettingsPermission]
    filterset_class = SkillFilterSet
