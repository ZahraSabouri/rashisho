# apps/access/api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.access.models import UserAdminAccess, UserScope, RegionCluster, ProjectCluster

User = get_user_model()

class UserAdminAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAdminAccess
        fields = ["id", "user", "sections"]

class UserScopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserScope
        fields = ["id", "user", "region_cluster", "project_cluster", "stage", "team_role_limit"]
