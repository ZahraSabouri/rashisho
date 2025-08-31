# apps/access/admin.py
from django.contrib import admin
from django.contrib.auth.models import Group
from .models import AccessPolicy
from .services import invalidate_policy_cache

@admin.register(AccessPolicy)
class AccessPolicyAdmin(admin.ModelAdmin):
    list_display = ("resource_type", "resource")
    filter_horizontal = ("roles",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_policy_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        invalidate_policy_cache()
