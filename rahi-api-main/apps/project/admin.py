from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.project import models


class ProjectStatusFilter(admin.SimpleListFilter):
    """Custom filter for project status"""
    title = 'وضعیت فعالیت'
    parameter_name = 'activation_status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'فعال'),
            ('inactive', 'غیرفعال'),
            ('selectable', 'قابل انتخاب'),
            ('hidden', 'مخفی'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        elif self.value() == 'inactive':
            return queryset.filter(is_active=False)
        elif self.value() == 'selectable':
            return queryset.filter(is_active=True, visible=True)
        elif self.value() == 'hidden':
            return queryset.filter(visible=False)
        return queryset


class TagAdmin(admin.ModelAdmin):
    """Admin interface for Tag model"""
    list_display = ['name', 'description', 'usage_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']

    def usage_count(self, obj):
        """Display how many projects use this tag"""
        count = obj.projects.count()
        color = '#dc3545' if count == 0 else '#007bff'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            color, count
        )
    usage_count.short_description = 'تعداد استفاده'

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).prefetch_related('projects')


class ProjectAdmin(admin.ModelAdmin):
    """Enhanced Project admin with activation status management"""
    
    list_display = [
        'title', 'company', 'status_indicator', 'visible', 'is_active', 
        'tag_count', 'study_field_count', 'allocations_count', 'created_at'
    ]
    list_filter = [
        ProjectStatusFilter, 'visible', 'is_active', 'study_fields', 
        'tags', 'created_at', 'company'
    ]
    search_fields = ['title', 'company', 'description', 'leader']
    filter_horizontal = ['study_fields', 'tags']
    readonly_fields = ['code', 'created_at', 'updated_at', 'status_display']
    ordering = ['-created_at']
    list_per_page = 25
    
    # Bulk actions
    actions = ['activate_projects', 'deactivate_projects', 'make_visible', 'make_hidden']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'company', 'leader', 'leader_position', 'code')
        }),
        ('محتوا و توضیحات', {
            'fields': ('description', 'image', 'video', 'file')
        }),
        ('تاریخ‌ها', {
            'fields': ('start_date', 'end_date'),
            'classes': ('collapse',)
        }),
        ('دسته‌بندی و تگ‌ها', {
            'fields': ('study_fields', 'tags'),
            'description': 'رشته‌های تحصیلی مرتبط و کلیدواژه‌های پروژه را انتخاب کنید'
        }),
        ('تنظیمات وضعیت', {
            'fields': ('is_active', 'visible', 'status_display'),
            'description': 'کنترل نمایش و فعالیت پروژه'
        }),
        ('سایر تنظیمات', {
            'fields': ('telegram_id',),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستم', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_indicator(self, obj):
        """Visual status indicator"""
        if not obj.visible:
            return format_html(
                '<span style="color: #666; font-weight: bold;">🙈 مخفی</span>'
            )
        elif not obj.is_active:
            return format_html(
                '<span style="color: #e74c3c; font-weight: bold;">❌ غیرفعال</span>'
            )
        else:
            return format_html(
                '<span style="color: #27ae60; font-weight: bold;">✅ فعال</span>'
            )
    status_indicator.short_description = 'وضعیت'
    
    def tag_count(self, obj):
        """Display number of tags"""
        count = obj.tag_count if hasattr(obj, 'tag_count') else obj.tags.count()
        return format_html(
            '<span style="background-color: #007bff; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            count
        )
    tag_count.short_description = 'تعداد تگ‌ها'
    
    def study_field_count(self, obj):
        """Display number of study fields"""
        count = obj.field_count if hasattr(obj, 'field_count') else obj.study_fields.count()
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            count
        )
    study_field_count.short_description = 'تعداد رشته‌ها'
    
    def allocations_count(self, obj):
        """Display number of allocations"""
        count = obj.allocation_count if hasattr(obj, 'allocation_count') else obj.allocations.count()
        color = '#dc3545' if count == 0 else '#17a2b8'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            color, count
        )
    allocations_count.short_description = 'تعداد تخصیص‌ها'
    
    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('tags', 'study_fields', 'allocations').annotate(
            tag_count=Count("tags", distinct=True),
            field_count=Count("study_fields", distinct=True),
            allocation_count=Count("allocations", distinct=True)
        )
    
    # Bulk Actions
    def activate_projects(self, request, queryset):
        """Bulk activate projects"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} پروژه فعال شد.')
    activate_projects.short_description = "فعال کردن پروژه‌های انتخابی"
    
    def deactivate_projects(self, request, queryset):
        """Bulk deactivate projects"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} پروژه غیرفعال شد.')
    deactivate_projects.short_description = "غیرفعال کردن پروژه‌های انتخابی"
    
    def make_visible(self, request, queryset):
        """Bulk make projects visible"""
        updated = queryset.update(visible=True)
        self.message_user(request, f'{updated} پروژه قابل مشاهده شد.')
    make_visible.short_description = "قابل مشاهده کردن پروژه‌های انتخابی"
    
    def make_hidden(self, request, queryset):
        """Bulk hide projects"""
        updated = queryset.update(visible=False)
        self.message_user(request, f'{updated} پروژه مخفی شد.')
    make_hidden.short_description = "مخفی کردن پروژه‌های انتخابی"


class ProjectAllocationAdmin(admin.ModelAdmin):
    """Admin for project allocations"""
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


# IMPORTANT: Unregister the existing Project model first, then register with new admin
try:
    admin.site.unregister(models.Project)
except admin.sites.NotRegistered:
    pass  # Project wasn't registered yet, which is fine

# Register models
admin.site.register(models.Tag, TagAdmin)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.ProjectAllocation, ProjectAllocationAdmin)
admin.site.register(models.FinalRepresentation)
admin.site.register(models.Scenario)
admin.site.register(models.Task)
admin.site.register(models.ProjectDerivatives)
admin.site.register(models.Team, TeamAdmin)
admin.site.register(models.TeamRequest, TeamRequestAdmin)
admin.site.register(models.UserScenarioTaskFile, UserScenarioTaskFileAdmin)