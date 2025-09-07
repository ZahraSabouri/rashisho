from django.db.models import Q
from django_filters.rest_framework import FilterSet, filters

from apps.project.models import Project, ProjectAllocation


class ProjectFilterSet(FilterSet):
    study_fields = filters.CharFilter(field_name="study_fields", method="filter_study_field")
    title = filters.CharFilter(lookup_expr="icontains")
    tags = filters.CharFilter(field_name="tags", method="filter_tags")
    company = filters.CharFilter(lookup_expr="icontains")
    search = filters.CharFilter(method="filter_search")
    tag_category = filters.CharFilter(field_name="tags__category", lookup_expr="exact")

    class Meta:
        model = Project
        exclude = ["image", "video", "file"]

    def filter_study_field(self, queryset, name, values):
        """Filter by study fields - supports comma-separated IDs"""
        values_list = values.split(",")
        final_qs = Project.objects.none()
        for value in values_list:
            try:
                final_qs |= Project.objects.filter(study_fields=value)
            except Exception:
                return queryset
        return final_qs

    def filter_tags(self, queryset, name, values):
        """Filter by tags - supports comma-separated tag IDs or names"""
        values_list = [v.strip() for v in values.split(",") if v.strip()]
        if not values_list:
            return queryset
        
        final_qs = Project.objects.none()
        for value in values_list:
            try:
                # Try to filter by ID first (if it's a number)
                if value.isdigit():
                    final_qs |= queryset.filter(tags__id=value)
                else:
                    # Filter by tag name (case-insensitive)
                    final_qs |= queryset.filter(tags__name__icontains=value)
            except Exception:
                continue
        
        return final_qs.distinct()

    def filter_search(self, queryset, name, value):
        """
        General search across multiple fields:
        - Project title
        - Project description  
        - Company name
        - Tag names
        - Leader name
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(title__icontains=value) |
            Q(description__icontains=value) |
            Q(company__icontains=value) |
            Q(tags__name__icontains=value) |
            Q(leader__icontains=value)
        ).distinct()


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
