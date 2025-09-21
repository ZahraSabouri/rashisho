from django.contrib.auth.models import Permission, Group
from rest_framework.viewsets import GenericViewSet, ModelViewSet
from rest_framework import mixins
from django.contrib.auth import get_user_model

from apps.manager.api.serializers import (
    PermissionSerializer,
    GroupSerializer,
    UserSerializer
)
from apps.manager.permissions import IsSuperUser

User = get_user_model()


class PermissionManagementViewSet(ModelViewSet):
    """
    ViewSet for managing permissions.
    """
    queryset = Permission.objects.all().select_related('content_type')
    serializer_class = PermissionSerializer
    permission_classes = [IsSuperUser]


class GroupModelViewSet(ModelViewSet):
    """
    API endpoint to list and create groups.
    Only accessible by superusers.
    """
    queryset = Group.objects.all().prefetch_related('permissions__content_type')
    serializer_class = GroupSerializer
    permission_classes = [IsSuperUser]


class UserStaffManagementViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet
):
    """
    API endpoint to manage user staff status.
    Only accessible by superusers.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsSuperUser]
