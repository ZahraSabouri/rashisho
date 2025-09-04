# apps/project/api/serializers/project_list.py
"""
List serializer for Projects with precomputed counts.
- Keeps responses light for list views.
- Reuses the existing attractiveness counter utility.
"""
from rest_framework import serializers
from apps.project.models import Project
from apps.project.services import count_project_attractiveness, is_selection_phase_active


class ProjectAnnotatedListSerializer(serializers.ModelSerializer):
    tags_count = serializers.IntegerField(read_only=True)
    allocations_count = serializers.IntegerField(read_only=True)

    # This one is computed (but cached in services.py)
    # Only exposed when PP (selection phase) is active.
    attractiveness = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "title", "code", "company", "leader",
            "tags_count", "allocations_count", "attractiveness",
        ]

    def get_attractiveness(self, obj):
        # Hide until the selection phase is active
        if not is_selection_phase_active():
            return None
        return count_project_attractiveness(obj.id)
