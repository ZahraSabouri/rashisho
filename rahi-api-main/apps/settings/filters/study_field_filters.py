from django_filters import rest_framework as filter
from apps.settings.models import StudyField

class StudyFieldFilter(filter.FilterSet):
    title = filter.CharFilter(lookup_expr='icontains')

    class Meta:
        model = StudyField
        fields = ['title']