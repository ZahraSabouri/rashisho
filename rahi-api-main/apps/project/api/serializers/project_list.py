from rest_framework import serializers
from apps.project.models import Project
from apps.project.services import can_show_attractiveness, compute_project_relatability, count_project_attractiveness, is_selection_phase_active


class ProjectAnnotatedListSerializer(serializers.ModelSerializer):
    tags_count = serializers.IntegerField(read_only=True)
    allocations_count = serializers.IntegerField(read_only=True)

    current_phase = serializers.CharField(read_only=True)
    can_be_selected = serializers.BooleanField(read_only=True)
    attractiveness = serializers.SerializerMethodField()

    relatability = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "title", "summary", "code", "company", "leader",
            "tags_count", "allocations_count", "attractiveness",
            "current_phase", "can_be_selected", "relatability"
        ]

    def get_attractiveness(self, obj):
        if can_show_attractiveness(obj):
            return count_project_attractiveness(obj.id)
        return None
    

    def get_relatability(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return {"score": 0, "matched_by": "none"}
        return compute_project_relatability(obj, user)
    

