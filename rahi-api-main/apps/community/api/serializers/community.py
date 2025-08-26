from rest_framework import serializers

from apps.account.models import User
from apps.common.serializers import CustomSlugRelatedField
from apps.community import models


class CommunityResourceSerializer(serializers.ModelSerializer):
    community = CustomSlugRelatedField(slug_field="title", queryset=models.Community.objects.all())

    class Meta:
        model = models.CommunityResource
        exclude = ["deleted", "deleted_at", "created_at", "updated_at"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["file"] = instance.file.url if instance.file else None
        rep["community"] = [
            {
                "value": instance.community.id,
                "text": instance.community.title,
                "manager": instance.community.manager.full_name,
            }
        ]
        return rep


class CommunitySerializer(serializers.ModelSerializer):
    manager = CustomSlugRelatedField(slug_field="full_name", queryset=User.objects.all(), required=False)
    representer_community = CustomSlugRelatedField(
        slug_field="title", queryset=models.Community.objects.all(), required=False
    )

    class Meta:
        model = models.Community
        exclude = ["deleted", "deleted_at"]
        read_only_fields = ["code", "manager"]
