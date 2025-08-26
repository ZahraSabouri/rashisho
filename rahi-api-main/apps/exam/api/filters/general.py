from django_filters.rest_framework import FilterSet, filters

from apps.exam.models import GeneralExam


class EntranceExamFilterSet(FilterSet):
    project = filters.CharFilter(field_name="project_id", lookup_expr="exact")
    mode = filters.CharFilter(field_name="mode", lookup_expr="exact")

    class Meta:
        model = GeneralExam
        exclude = ["project", "mode"]
