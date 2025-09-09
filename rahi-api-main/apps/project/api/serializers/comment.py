from rest_framework import serializers
from apps.comments.api.serializers import CommentSerializer


class ProjectCommentSerializer(CommentSerializer):
    project_name = serializers.SerializerMethodField(read_only=True)

    class Meta(CommentSerializer.Meta):
        fields = CommentSerializer.Meta.fields + ["project_name"]

    def get_project_name(self, obj):
        content_obj = getattr(obj, "content_object", None)
        return getattr(content_obj, "title", None)


class ProjectCommentReactionInputSerializer(serializers.Serializer):
    reaction_type = serializers.ChoiceField(choices=["LIKE", "DISLIKE"])
