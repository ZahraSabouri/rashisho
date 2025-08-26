from django.db.models import Q
from django_filters.rest_framework import FilterSet, filters

from apps.project.models import Project, ProjectAllocation


class ProjectFilterSet(FilterSet):
    study_fields = filters.CharFilter(field_name="study_fields", method="filter_study_field")
    title = filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Project
        exclude = ["image", "video", "file"]

    def filter_study_field(self, queryset, name, values):
        values_list = values.split(",")
        final_qs = Project.objects.none()
        for value in values_list:
            try:
                final_qs |= Project.objects.filter(study_fields=value)
            except Exception:
                return queryset

        return final_qs


class ProjectPriorityFilterSet(FilterSet):
    user = filters.CharFilter(field_name="user", method="filter_user")
    national_id = filters.CharFilter(field_name="user", method="filter_national_id")
    project = filters.CharFilter(field_name="project__id")

    class Meta:
        model = ProjectAllocation
        exclude = ["priority"]

    def filter_user(self, queryset, name, values):
        values_list = values.split(" ")
        result = ProjectAllocation.objects.none()
        for value in values_list:
            try:
                result |= ProjectAllocation.objects.filter(
                    Q(user__user_info__first_name__icontains=value) | Q(user__user_info__last_name__icontains=value)
                )
            except Exception:
                return queryset

        return result

    def filter_national_id(self, queryset, name, values):
        try:
            result = ProjectAllocation.objects.filter(user__user_info__national_id=values)
        except Exception:
            return queryset

        return result
