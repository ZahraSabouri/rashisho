from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.api.roles import Roles
from apps.community.models import Community
from apps.exam.services import belbin_finished
from apps.project.models import ProjectAllocation
from apps.resume.models import Resume


class ResumeStepPermission(BasePermission):
    def has_permission(self, request, view):
        try:
            return view.kwargs["resume_pk"] == str(request.user.resume.pk)
        except ObjectDoesNotExist:
            return False


class ResumePermission(BasePermission):
    def has_permission(self, request, view):
        community = Community.objects.filter(manager=request.user)

        if view.action == "list":
            if request.user and request.user.has_role([Roles.sys_god]):
                return True

            if community:
                return True

        if view.action == "retrieve":
            if request.user and request.user.has_role([Roles.sys_god]):
                return True

            obj = Resume.objects.filter(id=view.kwargs["pk"]).first()
            if community:
                if community == obj.user.community:
                    return True
            if ProjectAllocation.objects.filter(user=request.user).exists():
                if obj and request.user.project.project == obj.user.project.project:
                    return True

        return request.user.has_role([Roles.user]) is not None

    def has_object_permission(self, request, view, obj):
        if view.action in ["update", "partial_update", "destroy"]:
            return obj.user == request.user

        if view.action == "retrieve":
            community = Community.objects.filter(manager=request.user)
            if community:
                return (
                    obj.user == request.user
                    or request.user.has_role([Roles.sys_god])
                    or obj.user.project.project == request.user.project.project
                    or obj.user.community == request.user.created_communities
                )
            else:
                return (
                    obj.user == request.user
                    or request.user.has_role([Roles.sys_god])
                    or obj.user.project.project == request.user.project.project
                )

        return False


class IsSysgod(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.user.has_role([Roles.sys_god])


class IsUser(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.user.has_role([Roles.user])


class ResumeFinishedPermission(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.user.has_role([Roles.sys_god]) or request.user.resume.resume_completed


class IsAdminOrReadOnlyPermission(BasePermission):
    def has_permission(self, request, view) -> bool:

        action = getattr(view, "action", None)
        if action is None:
            if request.method in SAFE_METHODS:
                return True
            return request.user.has_role([Roles.sys_god])

        if action in ["create", "update", "partial_update", "destroy", "project_allocate_excel"]:
            return request.user.has_role([Roles.sys_god])

        return True


class NeoPermission(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.user.has_role([Roles.sys_god]) or belbin_finished(request.user)


class SettingsPermission(BasePermission):
    def has_permission(self, request, view) -> bool:
        if view.action in ["list", "retrieve", "get_active_list"]:
            return True

        return request.user.has_role([Roles.sys_god])


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class StartedExamPermission(BasePermission):
    def has_permission(self, request, view) -> float:
        exam_answer = view._user_answer().get_general_by_exam(view._exam())
        if exam_answer == {} or exam_answer["status"] == "started":
            return True
        elif request.method in SAFE_METHODS:
            return True
        return False


class CommunityPermission(BasePermission):
    def has_permission(self, request, view) -> bool:
        if view.action == "list":
            return request.user.has_role([Roles.sys_god])
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if view.action == "retrieve":
            return request.user.is_authenticated
        return request.user == obj.manager or request.user.has_role([Roles.sys_god])
