# apps/access/models.py
from django.db import models
from django.contrib.auth.models import Group
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField
from apps.common.models import BaseModel

class AccessPolicy(BaseModel):
    """
    مدل Policy داینامیک:
    - resource_type: 'view_name' | 'path_regex'
    - resource: نام view (مثل 'project:project-priority-list') یا الگوی regex مسیر
    - methods: لیست متدها ['GET','POST',...] یا ['*']
    - roles: نقش‌هایی که اجازه دارند (Groupهای جنگو)
    - conditions: شرط‌های ABAC (JSON): {min_stage, team_roles, region_cluster_ids, project_cluster_ids, admin_sections}
    """
    VIEW_NAME = "view_name"
    PATH_REGEX = "path_regex"

    resource_type = models.CharField(max_length=20, choices=[(VIEW_NAME, VIEW_NAME), (PATH_REGEX, PATH_REGEX)])
    resource = models.CharField(max_length=255)
    methods = ArrayField(models.CharField(max_length=10), default=list)
    roles = models.ManyToManyField(Group, blank=True, related_name="policies")
    conditions = JSONField(default=dict, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "سیاست دسترسی"
        verbose_name_plural = "سیاست‌های دسترسی"

    def __str__(self):
        return f"{self.resource_type}:{self.resource} {self.methods}"
