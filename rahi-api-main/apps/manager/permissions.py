from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


class BaseCustomPermission(permissions.BasePermission):
    """
    Base custom permission class to be extended by other permission classes.
    """

    def has_permission(self, request, view):
        # check if the user exists and is authenticated and active
        has_perm = super().has_permission(request, view)
        return has_perm

    def has_object_permission(self, request, view, obj):
        # check if the user exists and is authenticated and active
        has_perm = super().has_object_permission(request, view, obj)
        return has_perm


class IsSuperUser(BaseCustomPermission):
    """
    Custom permission to only allow superusers to access views.
    """

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_authenticated and request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        return (super().has_object_permission(request, view, obj) and
                request.user.is_authenticated and
                request.user.is_superuser)


class IsStaffUser(BaseCustomPermission):
    """
    Custom permission to only allow staff users to access views.
    """

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_authenticated and request.user.is_staff

    def has_object_permission(self, request, view, obj):
        return (super().has_object_permission(request, view, obj)
                and request.user.is_authenticated and request.user.is_staff)


class IsSuperUserOrStaff(BaseCustomPermission):
    """
    Custom permission to allow access to superusers or staff users.
    """

    def has_permission(self, request, view):
        return super().has_permission(request, view) and (request.user.is_superuser or request.user.is_staff)

    def has_object_permission(self, request, view, obj):
        return super().has_object_permission(request, view, obj) and (
                request.user.is_superuser or request.user.is_staff)
