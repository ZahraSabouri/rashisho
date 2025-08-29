from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from apps.project import models


class TagAdmin(admin.ModelAdmin):
    """
    Admin interface for Tag model.
    Shows tag usage statistics and management options.
    """
    
    list_display = ['name', 'description_short', 'project_count', 'visible_project_count', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'description']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('اطلاعات تگ', {
            'fields': ('name', 'description')
        }),
        ('اطلاعات سیستم', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def description_short(self, obj):
        """Display shortened description"""
        if obj.description:
            return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
        return '-'
    description_short.short_description = 'توضیحات مختصر'
    
    def project_count(self, obj):
        """Display total number of projects using this tag"""
        count = obj.total_project_count if hasattr(obj, 'total_project_count') else obj.projects.count()
        return format_html(
            '<span style="color: {};">{}</span>',
            '#28a745' if count > 0 else '#dc3545',
            count
        )
    project_count.short_description = 'کل پروژه‌ها'
    
    def visible_project_count(self, obj):
        """Display number of visible projects using this tag"""
        count = obj.visible_project_count if hasattr(obj, 'visible_project_count') else obj.projects.filter(visible=True).count()
        return format_html(
            '<span style="color: {};">{}</span>',
            '#28a745' if count > 0 else '#6c757d',
            count
        )
    visible_project_count.short_description = 'پروژه‌های قابل نمایش'
    
    def get_queryset(self, request):
        """Optimize queryset with project count annotations"""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            total_project_count=Count("projects", distinct=True),
            visible_project_count=Count("projects", filter=models.Q(projects__visible=True), distinct=True)
        )


class ProjectAdmin(admin.ModelAdmin):
    """
    Updated Project admin interface with tags support.
    """
    
    list_display = ['title', 'company', 'visible', 'tag_count', 'study_field_count', 'created_at']
    list_filter = ['visible', 'study_fields', 'tags', 'created_at', 'company']
    search_fields = ['title', 'company', 'description', 'leader']
    filter_horizontal = ['study_fields', 'tags']  # This creates nice multi-select widgets
    readonly_fields = ['code', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'company', 'leader', 'leader_position', 'code')
        }),
        ('محتوا و توضیحات', {
            'fields': ('description', 'image', 'video', 'file')
        }),
        ('دسته‌بندی و تگ‌ها', {
            'fields': ('study_fields', 'tags'),
            'description': 'رشته‌های تحصیلی مرتبط و کلیدواژه‌های پروژه را انتخاب کنید'
        }),
        ('تنظیمات', {
            'fields': ('visible', 'telegram_id')
        }),
        ('اطلاعات سیستم', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def tag_count(self, obj):
        """Display number of tags for this project"""
        count = obj.tag_count if hasattr(obj, 'tag_count') else obj.tags.count()
        return format_html(
            '<span style="background-color: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;">{}</span>',
            count
        )
    tag_count.short_description = 'تعداد تگ‌ها'
    
    def study_field_count(self, obj):
        """Display number of study fields for this project"""
        count = obj.field_count if hasattr(obj, 'field_count') else obj.study_fields.count()
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;">{}</span>',
            count
        )
    study_field_count.short_description = 'تعداد رشته‌ها'
    
    def get_queryset(self, request):
        """Optimize queryset with count annotations"""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('tags', 'study_fields').annotate(
            tag_count=Count("tags", distinct=True),
            field_count=Count("study_fields", distinct=True)
        )


class ProjectAllocationAdmin(admin.ModelAdmin):
    search_fields = ["user__id", "user__user_info__national_id"]

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct


class TeamAdmin(admin.ModelAdmin):
    search_fields = ["title"]


class TeamRequestAdmin(admin.ModelAdmin):
    search_fields = ["user__username", "team__title", "status", "user_role"]


class UserScenarioTaskFileAdmin(admin.ModelAdmin):
    search_fields = ["user__user_info__national_id"]


admin.site.register(models.Tag, TagAdmin)  # NEW

# admin.site.unregister(models.Project)
admin.site.register(models.Project, ProjectAdmin)  # UPDATED

# Keep your existing registrations:
admin.site.register(models.ProjectAllocation, ProjectAllocationAdmin)
admin.site.register(models.FinalRepresentation)
admin.site.register(models.Scenario)
admin.site.register(models.Task)
admin.site.register(models.ProjectDerivatives)
admin.site.register(models.Team, TeamAdmin)
admin.site.register(models.TeamRequest, TeamRequestAdmin)
admin.site.register(models.UserScenarioTaskFile, UserScenarioTaskFileAdmin)