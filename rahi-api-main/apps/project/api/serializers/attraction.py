from rest_framework import serializers
from apps.project.models import Project, ProjectAttractiveness

class AttractionCreateSerializer(serializers.Serializer):
    project = serializers.UUIDField()
    priority = serializers.IntegerField(required=False, min_value=1, max_value=5)

    def validate_project(self, value):
        if not Project.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Project not found or inactive.")
        return value


class AttractionReorderSerializer(serializers.Serializer):
    # ordered list of project IDs (top to bottom)
    projects = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, max_length=5
    )

    def validate(self, attrs):
        items = attrs["projects"]
        if len(items) != len(set(items)):
            raise serializers.ValidationError("Duplicate project IDs are not allowed.")
        # ensure all belong to user already
        user = self.context["request"].user
        existing = set(
            ProjectAttractiveness.objects.filter(user=user, project_id__in=items)
            .values_list("project_id", flat=True)
        )
        missing = [str(pid) for pid in items if pid not in existing]
        if missing:
            raise serializers.ValidationError({"projects": f"Not in your list: {', '.join(missing)}"})
        return attrs
