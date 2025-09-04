# apps/project/api/serializers/project_list.py
"""
List serializer for Projects with precomputed counts.
- Keeps responses light for list views.
- Reuses the existing attractiveness counter utility.
"""
from rest_framework import serializers
from apps.project.models import Project
from apps.project.services import can_show_attractiveness, count_project_attractiveness, is_selection_phase_active


class ProjectAnnotatedListSerializer(serializers.ModelSerializer):
    tags_count = serializers.IntegerField(read_only=True)
    allocations_count = serializers.IntegerField(read_only=True)

    # Phase information
    current_phase = serializers.CharField(read_only=True)
    can_be_selected = serializers.BooleanField(read_only=True)
    
    # Computed attractiveness per project
    attractiveness = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "title", "code", "company", "leader",
            "tags_count", "allocations_count", "attractiveness",
            "current_phase", "can_be_selected"
        ]

    def get_attractiveness(self, obj):
        """Show attractiveness if project phase allows it"""
        if can_show_attractiveness(obj):
            return count_project_attractiveness(obj.id)
        return None
