from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.manager.api.views import (
    PermissionManagementViewSet,
    GroupModelViewSet, UserStaffManagementViewSet,
)

app_name = "manager"

# Router for ViewSets

router = DefaultRouter()
router.register(r'permissions', PermissionManagementViewSet, basename='permissions')
router.register(r'groups', GroupModelViewSet, basename='groups')
router.register(r'users', UserStaffManagementViewSet, basename='users')
urlpatterns = [path('', include(router.urls)), ]
