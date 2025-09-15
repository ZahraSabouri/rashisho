from datetime import timezone
from pyexpat.errors import messages
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.project import models

from apps.project.models import ProjectAttractiveness

@admin.register(models.TagCategory)
class TagCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "created_at")
    search_fields = ("code", "title")


@admin.register(ProjectAttractiveness)
class ProjectAttractivenessAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "user", "created_at")
    search_fields = ("project__title", "user__username", "user__user_info__first_name", "user__user_info__last_name")
    autocomplete_fields = ("project", "user")


class ProjectStatusFilter(admin.SimpleListFilter):
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
    list_display = ['name', 'description', 'usage_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']

    def usage_count(self, obj):
        count = obj.projects.count()
        color = '#dc3545' if count == 0 else '#007bff'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            color, count
        )
    usage_count.short_description = 'تعداد استفاده'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('projects')


class ProjectAdmin(admin.ModelAdmin):
    
    list_display = [
        'title', 'company', 'status_indicator', 'visible', 'is_active', 
        'tag_count', 'study_field_count', 'allocations_count', 'created_at',
        'current_phase_display', 'selection_dates_display',
        'attractiveness_count'
    ]
    list_filter = [
        ProjectStatusFilter, 'visible', 'is_active', 'study_fields', 
        'tags', 'created_at', 'company', 'selection_phase', 'selection_start', 'selection_end'
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
        ('مدیریت فاز', {
            'fields': [
                'selection_phase', 'auto_phase_transition',
                'selection_start', 'selection_end'
            ],
            'classes': ['collapse']
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
    
    actions = [
        'activate_selection_phase',
        'finish_selection_phase', 
        'reset_to_before_selection',
        'enable_auto_transition',
        'disable_auto_transition'
    ]

    def current_phase_display(self, obj):
        phase_color = {
            'BEFORE': '🔴',
            'ACTIVE': '🟢', 
            'FINISHED': '🟡'
        }
        icon = phase_color.get(obj.current_phase, '⚪')
        return f"{icon} {obj.phase_display}"
    current_phase_display.short_description = "فاز فعلی"
    
    def selection_dates_display(self, obj):
        if obj.selection_start and obj.selection_end:
            start = obj.selection_start.strftime("%m/%d %H:%M")
            end = obj.selection_end.strftime("%m/%d %H:%M") 
            return f"{start} - {end}"
        elif obj.selection_start:
            return f"شروع: {obj.selection_start.strftime('%m/%d %H:%M')}"
        elif obj.selection_end:
            return f"پایان: {obj.selection_end.strftime('%m/%d %H:%M')}"
        return "-"
    selection_dates_display.short_description = "تاریخ‌های انتخاب"
    
    def attractiveness_count(self, obj):
        from apps.project.services import count_project_attractiveness
        if obj.show_attractiveness:
            return count_project_attractiveness(obj.id)
        return "-"
    attractiveness_count.short_description = "جذابیت"
    
    def activate_selection_phase(self, request, queryset):
        updated = queryset.update(
            selection_phase=models.ProjectPhase.SELECTION_ACTIVE,
            selection_start=timezone.now()
        )
        self.message_user(
            request, 
            f'{updated} پروژه به فاز انتخاب فعال تغییر یافت.',
            messages.SUCCESS
        )
    activate_selection_phase.short_description = "فعال‌سازی فاز انتخاب"
    
    def finish_selection_phase(self, request, queryset):
        updated = queryset.update(
            selection_phase=models.ProjectPhase.SELECTION_FINISHED,
            selection_end=timezone.now()
        )
        self.message_user(
            request,
            f'{updated} پروژه به فاز پایان انتخاب تغییر یافت.',
            messages.SUCCESS
        )
    finish_selection_phase.short_description = "پایان فاز انتخاب"
    
    def reset_to_before_selection(self, request, queryset):
        updated = queryset.update(
            selection_phase=models.ProjectPhase.BEFORE_SELECTION
        )
        self.message_user(
            request,
            f'{updated} پروژه به فاز قبل از انتخاب بازگردانده شد.',
            messages.INFO
        )
    reset_to_before_selection.short_description = "بازگشت به قبل از انتخاب"
    
    def enable_auto_transition(self, request, queryset):
        updated = queryset.update(auto_phase_transition=True)
        self.message_user(
            request,
            f'تغییر خودکار فاز برای {updated} پروژه فعال شد.',
            messages.SUCCESS
        )
    enable_auto_transition.short_description = "فعال‌سازی تغییر خودکار فاز"
    
    def disable_auto_transition(self, request, queryset):
        updated = queryset.update(auto_phase_transition=False)
        self.message_user(
            request,
            f'تغییر خودکار فاز برای {updated} پروژه غیرفعال شد.',
            messages.INFO
        )
    disable_auto_transition.short_description = "غیرفعال‌سازی تغییر خودکار فاز"

    def status_indicator(self, obj):
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
        count = obj.tag_count if hasattr(obj, 'tag_count') else obj.tags.count()
        return format_html(
            '<span style="background-color: #007bff; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            count
        )
    tag_count.short_description = 'تعداد تگ‌ها'
    
    def study_field_count(self, obj):
        count = obj.field_count if hasattr(obj, 'field_count') else obj.study_fields.count()
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            count
        )
    study_field_count.short_description = 'تعداد رشته‌ها'
    
    def allocations_count(self, obj):
        count = obj.allocation_count if hasattr(obj, 'allocation_count') else obj.allocations.count()
        color = '#dc3545' if count == 0 else '#17a2b8'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            color, count
        )
    allocations_count.short_description = 'تعداد تخصیص‌ها'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('tags', 'study_fields', 'allocations').annotate(
            tag_count=Count("tags", distinct=True),
            field_count=Count("study_fields", distinct=True),
            allocation_count=Count("allocations", distinct=True)
        )
    
    # Bulk Actions
    def activate_projects(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} پروژه فعال شد.')
    activate_projects.short_description = "فعال کردن پروژه‌های انتخابی"
    
    def deactivate_projects(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} پروژه غیرفعال شد.')
    deactivate_projects.short_description = "غیرفعال کردن پروژه‌های انتخابی"
    
    def make_visible(self, request, queryset):
        updated = queryset.update(visible=True)
        self.message_user(request, f'{updated} پروژه قابل مشاهده شد.')
    make_visible.short_description = "قابل مشاهده کردن پروژه‌های انتخابی"
    
    def make_hidden(self, request, queryset):
        updated = queryset.update(visible=False)
        self.message_user(request, f'{updated} پروژه مخفی شد.')
    make_hidden.short_description = "مخفی کردن پروژه‌های انتخابی"


class ProjectAllocationAdmin(admin.ModelAdmin):
    search_fields = ["user__id", "user__user_info__national_id"]

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct


class TeamAdmin(admin.ModelAdmin):
    search_fields = ["title"]


class TeamRequestAdmin(admin.ModelAdmin):
    search_fields = ["user__username", "team__title", "status", "user_role"]


class TeamBuildingVideoButtonInline(admin.TabularInline):
    model = models.TeamBuildingVideoButton
    extra = 1
    fields = ('title', 'video_url', 'order')


@admin.register(models.TeamBuildingAnnouncement)
class TeamBuildingAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'order', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'content')
    ordering = ('order', '-created_at')
    inlines = [TeamBuildingVideoButtonInline]
    
    fields = ('title', 'content', 'is_active', 'order')


class UserScenarioTaskFileAdmin(admin.ModelAdmin):
    search_fields = ["user__user_info__national_id"]


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