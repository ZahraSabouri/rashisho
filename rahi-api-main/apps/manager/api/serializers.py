from django.contrib.auth.models import Permission, Group
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model with content type details."""
    content_type_name = serializers.CharField(source='content_type.name', read_only=True)

    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'content_type_name']
        read_only_fields = ['id', 'content_type_name']


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Group model with permission details."""
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions', 'permission_ids']
        read_only_fields = ['id',  'permissions']

    def validate_permission_ids(self, value):
        """Validate that all permission IDs exist."""
        if not value:
            return value

        existing_ids = set(Permission.objects.filter(id__in=value).values_list('id', flat=True))
        provided_ids = set(value)
        invalid_ids = provided_ids - existing_ids

        if invalid_ids:
            raise serializers.ValidationError(
                f"The following permission IDs do not exist: {invalid_ids}"
            )

        return value

    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_ids', [])
        group = super().create(validated_data)
        if permission_ids:
            group.permissions.set(permission_ids)
        return group

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_ids', None)
        instance = super().update(instance, validated_data)
        if permission_ids is not None:
            instance.permissions.set(permission_ids)
        return instance


class UserSerializer(serializers.ModelSerializer):
    """Serializer for updating user staff status."""
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    group_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    permissions = PermissionSerializer(many=True, read_only=True)
    groups = GroupSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'is_staff', 'is_active', 'permission_ids', 'group_ids', 'permissions', 'groups']
        read_only_fields = ['id', 'email', 'permissions', 'groups']

    def validate_permission_ids(self, value):
        """Validate that all permission IDs exist."""
        if not value:
            return value

        existing_ids = set(Permission.objects.filter(id__in=value).values_list('id', flat=True))
        provided_ids = set(value)
        invalid_ids = provided_ids - existing_ids

        if invalid_ids:
            raise serializers.ValidationError(
                f"The following permission IDs do not exist: {invalid_ids}"
            )

        return value

    def validate_group_ids(self, value):
        """Validate that all group IDs exist."""
        if not value:
            return value

        existing_ids = set(Group.objects.filter(id__in=value).values_list('id', flat=True))
        provided_ids = set(value)
        invalid_ids = provided_ids - existing_ids

        if invalid_ids:
            raise serializers.ValidationError(
                f"The following group IDs do not exist: {invalid_ids}"
            )

        return value

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_ids', None)
        group_ids = validated_data.pop('group_ids', None)
        instance = super().update(instance, validated_data)
        if permission_ids is not None:
            instance.user_permissions.set(permission_ids)
        if group_ids is not None:
            instance.groups.set(group_ids)
        return instance
