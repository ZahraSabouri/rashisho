from apps.manager.permissions import BaseCustomPermission


class ProjectPermission(BaseCustomPermission):
    def has_permission(self, request, view):
        if view.action in ["list", "retrieve"]:
            return super().has_permission(request, view)
        return False

    def has_object_permission(self, request, view, obj):
        if view.action in ["retrieve"]:
            if obj.groups.exists():
                if not request.user.is_authenticated:
                    return False
                user_group_ids = request.user.groups.values_list("id", flat=True)
                return obj.groups.filter(id__in=user_group_ids).exists()
            return True
        return False
