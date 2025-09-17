from datetime import timezone
from pyexpat.errors import messages
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.project import models
from apps.account.models import User

from apps.project.models import ProjectAttractiveness
from apps.project.models import (
    TeamChatMessage, TeamOnlineMeeting, TeamUnstableTask
)

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


@admin.register(TeamChatMessage)
class TeamChatMessageAdmin(admin.ModelAdmin):
    """Admin interface for team chat messages"""
    list_display = [
        'team_link', 'user_name', 'message_preview', 
        'created_at', 'is_edited', 'edited_at'
    ]
    list_filter = [
        'team__team_building_stage', 'is_edited', 'created_at',
        'team__project'
    ]
    search_fields = [
        'team__title', 'team__team_code', 'user__full_name', 
        'user__user_info__mobile_number', 'message'
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['team', 'user']
    date_hierarchy = 'created_at'
    
    def team_link(self, obj):
        url = reverse('admin:project_team_change', args=[obj.team.id])
        return format_html('<a href="{}">{} ({})</a>', 
                         url, obj.team.title, obj.team.team_code)
    team_link.short_description = 'تیم'
    team_link.admin_order_field = 'team__title'
    
    def user_name(self, obj):
        return obj.user.full_name
    user_name.short_description = 'کاربر'
    user_name.admin_order_field = 'user__full_name'
    
    def message_preview(self, obj):
        preview = obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
        if obj.is_edited:
            return format_html('<span style="color: orange;">{} <em>(ویرایش شده)</em></span>', preview)
        return preview
    message_preview.short_description = 'پیام'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('team', 'user')


@admin.register(TeamOnlineMeeting)
class TeamOnlineMeetingAdmin(admin.ModelAdmin):
    """Admin interface for team online meetings"""
    list_display = [
        'team_link', 'title', 'meeting_link_preview', 
        'scheduled_for', 'is_active', 'created_by_name', 'created_at'
    ]
    list_filter = [
        'is_active', 'team__team_building_stage', 'scheduled_for', 
        'created_at', 'team__project'
    ]
    search_fields = [
        'team__title', 'team__team_code', 'title', 
        'description', 'created_by__full_name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['team', 'created_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('اطلاعات جلسه', {
            'fields': ('team', 'title', 'description')
        }),
        ('تنظیمات جلسه', {
            'fields': ('meeting_url', 'scheduled_for', 'is_active')
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def team_link(self, obj):
        url = reverse('admin:project_team_change', args=[obj.team.id])
        return format_html('<a href="{}">{} ({})</a>', 
                         url, obj.team.title, obj.team.team_code)
    team_link.short_description = 'تیم'
    team_link.admin_order_field = 'team__title'
    
    def meeting_link_preview(self, obj):
        if obj.meeting_url:
            return format_html('<a href="{}" target="_blank">🔗 لینک جلسه</a>', obj.meeting_url)
        return '-'
    meeting_link_preview.short_description = 'لینک'
    
    def created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else '-'
    created_by_name.short_description = 'ایجاد شده توسط'
    created_by_name.admin_order_field = 'created_by__full_name'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('team', 'created_by')
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TeamUnstableTask)
class TeamUnstableTaskAdmin(admin.ModelAdmin):
    """Admin interface for team unstable tasks"""
    list_display = [
        'team_link', 'title', 'assigned_to_name', 'due_date', 
        'completion_status', 'created_at'
    ]
    list_filter = [
        'is_completed', 'team__team_building_stage', 'due_date',
        'created_at', 'team__project'
    ]
    search_fields = [
        'team__title', 'team__team_code', 'title', 'description',
        'assigned_to__full_name'
    ]
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    raw_id_fields = ['team', 'assigned_to']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('اطلاعات کار', {
            'fields': ('team', 'title', 'description', 'file')
        }),
        ('واگذاری و مهلت', {
            'fields': ('assigned_to', 'due_date')
        }),
        ('وضعیت تکمیل', {
            'fields': ('is_completed', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def team_link(self, obj):
        url = reverse('admin:project_team_change', args=[obj.team.id])
        return format_html('<a href="{}">{} ({})</a>', 
                         url, obj.team.title, obj.team.team_code)
    team_link.short_description = 'تیم'
    team_link.admin_order_field = 'team__title'
    
    def assigned_to_name(self, obj):
        if obj.assigned_to:
            url = reverse('admin:account_user_change', args=[obj.assigned_to.id])
            return format_html('<a href="{}">{}</a>', url, obj.assigned_to.full_name)
        return '-'
    assigned_to_name.short_description = 'واگذار شده به'
    assigned_to_name.admin_order_field = 'assigned_to__full_name'
    
    def completion_status(self, obj):
        if obj.is_completed:
            return format_html(
                '<span style="color: green;">✅ تکمیل شده</span><br><small>{}</small>',
                obj.completed_at.strftime('%Y-%m-%d %H:%M') if obj.completed_at else ''
            )
        elif obj.due_date:
            from django.utils import timezone
            if obj.due_date < timezone.now().date():
                return format_html('<span style="color: red;">⏰ گذشته از مهلت</span>')
            else:
                return format_html('<span style="color: orange;">⏳ در انتظار</span>')
        return format_html('<span style="color: gray;">📋 در انتظار</span>')
    completion_status.short_description = 'وضعیت'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('team', 'assigned_to')


# Add these inline admin classes to your existing TeamAdmin
class TeamChatMessageInline(admin.TabularInline):
    """Inline for viewing recent team chat messages"""
    model = TeamChatMessage
    extra = 0
    readonly_fields = ['user', 'message', 'created_at', 'is_edited']
    fields = ['user', 'message', 'created_at', 'is_edited']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').order_by('-created_at')[:10]
    
    def has_add_permission(self, request, obj=None):
        return False


class TeamOnlineMeetingInline(admin.TabularInline):
    """Inline for team online meetings"""
    model = TeamOnlineMeeting
    extra = 0
    fields = ['title', 'meeting_url', 'scheduled_for', 'is_active']
    readonly_fields = ['created_at']


class TeamUnstableTaskInline(admin.TabularInline):
    """Inline for team unstable tasks"""
    model = TeamUnstableTask
    extra = 0
    fields = ['title', 'assigned_to', 'due_date', 'is_completed']
    readonly_fields = ['created_at', 'completed_at']


class TeamAdmin(admin.ModelAdmin):
    search_fields = ["title"]
    inlines = [
        TeamOnlineMeetingInline,
        TeamUnstableTaskInline,
        TeamChatMessageInline,
    ]


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


from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from apps.project.models import (
    TeamBuildingSettings, TeamBuildingStageDescription
)

@admin.register(TeamBuildingSettings)
class TeamBuildingSettingsAdmin(admin.ModelAdmin):
    """
    Admin interface for the 12-stage team building control system
    """
    list_display = [
        'stage_control_display', 'is_enabled', 'min_team_size', 'max_team_size',
        'prevent_repeat_teammates', 'allow_auto_completion', 'formation_deadline_hours'
    ]
    list_filter = [
        'stage', 'control_type', 'is_enabled', 'prevent_repeat_teammates', 
        'allow_auto_completion'
    ]
    search_fields = ['stage', 'control_type', 'custom_description']
    list_editable = ['is_enabled', 'prevent_repeat_teammates', 'allow_auto_completion']
    
    fieldsets = (
        ('اطلاعات کنترل', {
            'fields': ('stage', 'control_type', 'is_enabled')
        }),
        ('تنظیمات تیم', {
            'fields': ('min_team_size', 'max_team_size', 'formation_deadline_hours'),
            'classes': ('collapse',)
        }),
        ('قوانین تیم‌سازی', {
            'fields': ('prevent_repeat_teammates', 'allow_auto_completion'),
            'classes': ('collapse',)
        }),
        ('توضیحات سفارشی', {
            'fields': ('custom_description',),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def stage_control_display(self, obj):
        """Display stage and control type together"""
        color = '#4CAF50' if obj.is_enabled else '#f44336'
        status = 'فعال' if obj.is_enabled else 'غیرفعال'
        
        return format_html(
            '<strong>{} - {}</strong><br>'
            '<span style="color: {}; font-size: 11px;">● {}</span>',
            obj.get_stage_display(),
            obj.get_control_type_display(),
            color,
            status
        )
    stage_control_display.short_description = 'مرحله و کنترل'
    stage_control_display.admin_order_field = 'stage'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()
    
    class Media:
        css = {
            'all': ('admin/css/team_building_admin.css',)  # Add custom CSS if needed
        }


@admin.register(TeamBuildingStageDescription)
class TeamBuildingStageDescriptionAdmin(admin.ModelAdmin):
    """
    Admin interface for managing custom descriptions of team building pages
    """
    list_display = [
        'page_type_display', 'title', 'is_active', 'description_preview', 'updated_at'
    ]
    list_filter = ['page_type', 'is_active', 'created_at']
    search_fields = ['title', 'description', 'page_type']
    list_editable = ['is_active']
    
    fieldsets = (
        ('اطلاعات صفحه', {
            'fields': ('page_type', 'title', 'is_active')
        }),
        ('توضیحات', {
            'fields': ('description',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def page_type_display(self, obj):
        """Enhanced display of page type"""
        return format_html(
            '<strong>{}</strong><br>'
            '<span style="color: #666; font-size: 11px;">{}</span>',
            obj.get_page_type_display(),
            obj.page_type
        )
    page_type_display.short_description = 'نوع صفحه'
    page_type_display.admin_order_field = 'page_type'
    
    def description_preview(self, obj):
        """Show preview of description"""
        preview = obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
        return format_html('<span style="color: #666;">{}</span>', preview)
    description_preview.short_description = 'پیش‌نمایش توضیحات'


# Enhanced Team admin with new functionality
class TeamBuildingStageFilter(admin.SimpleListFilter):
    title = 'نوع مرحله تیم‌سازی'
    parameter_name = 'team_type'

    def lookups(self, request, model_admin):
        return (
            ('unstable', 'تیم‌های ناپایدار (مراحل 1-3)'),
            ('stable', 'تیم‌های پایدار (مرحله 4)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'unstable':
            return queryset.filter(team_building_stage__in=[1, 2, 3])
        elif self.value() == 'stable':
            return queryset.filter(team_building_stage=4)


# Add to existing TeamAdmin class
def enhanced_team_admin():
    """
    Enhance existing TeamAdmin with new functionality
    Add these methods to your existing TeamAdmin class:
    """
    
    # Add these to list_display
    def team_type_display(self, obj):
        """Display team type (stable/unstable)"""
        if obj.team_building_stage in [1, 2, 3]:
            return format_html(
                '<span style="color: #FF9800; font-weight: bold;">ناپایدار - مرحله {}</span>',
                obj.team_building_stage
            )
        else:
            return format_html(
                '<span style="color: #4CAF50; font-weight: bold;">پایدار - مرحله {}</span>',
                obj.team_building_stage
            )
    team_type_display.short_description = 'نوع تیم'
    team_type_display.admin_order_field = 'team_building_stage'
    
    def formation_status(self, obj):
        """Display formation status"""
        formation_enabled = obj.is_formation_allowed()
        page_enabled = obj.is_team_page_accessible()
        
        status_html = []
        if formation_enabled:
            status_html.append('<span style="color: #4CAF50;">● تشکیل فعال</span>')
        else:
            status_html.append('<span style="color: #f44336;">● تشکیل غیرفعال</span>')
        
        if page_enabled:
            status_html.append('<span style="color: #4CAF50;">● صفحه فعال</span>')
        else:
            status_html.append('<span style="color: #f44336;">● صفحه غیرفعال</span>')
        
        return format_html('<br>'.join(status_html))
    formation_status.short_description = 'وضعیت تشکیل'
    
    def team_completion_status(self, obj):
        """Display completion status for unstable teams"""
        if not obj.is_unstable_team():
            return format_html('<span style="color: #666;">-</span>')
        
        can_auto_complete = obj.can_be_auto_completed()
        deadline = obj.get_formation_deadline()
        
        status_parts = []
        if can_auto_complete:
            status_parts.append('<span style="color: #4CAF50;">تکمیل خودکار: فعال</span>')
        else:
            status_parts.append('<span style="color: #f44336;">تکمیل خودکار: غیرفعال</span>')
        
        if deadline:
            from django.utils import timezone
            if deadline > timezone.now():
                status_parts.append(f'<span style="color: #FF9800;">مهلت: {deadline.strftime("%Y-%m-%d %H:%M")}</span>')
            else:
                status_parts.append('<span style="color: #f44336;">مهلت: منقضی شده</span>')
        
        return format_html('<br>'.join(status_parts))
    team_completion_status.short_description = 'وضعیت تکمیل'
    
    # Add to list_filter
    list_filter = [
        TeamBuildingStageFilter,  # Add this to existing filters
        'team_building_stage',
        # ... other existing filters
    ]
    
    # Add actions
    def enable_formation_for_stage(self, request, queryset):
        """Enable formation for selected teams' stages"""
        stages = queryset.values_list('team_building_stage', flat=True).distinct()
        
        for stage in stages:
            TeamBuildingSettings.objects.filter(
                stage=stage, control_type='formation'
            ).update(is_enabled=True)
        
        self.message_user(request, f'تشکیل تیم برای مراحل {list(stages)} فعال شد')
    enable_formation_for_stage.short_description = 'فعال کردن تشکیل تیم برای این مراحل'
    
    def disable_formation_for_stage(self, request, queryset):
        """Disable formation for selected teams' stages"""
        stages = queryset.values_list('team_building_stage', flat=True).distinct()
        
        for stage in stages:
            TeamBuildingSettings.objects.filter(
                stage=stage, control_type='formation'
            ).update(is_enabled=False)
        
        self.message_user(request, f'تشکیل تیم برای مراحل {list(stages)} غیرفعال شد')
    disable_formation_for_stage.short_description = 'غیرفعال کردن تشکیل تیم برای این مراحل'
    
    actions = [
        'enable_formation_for_stage',
        'disable_formation_for_stage',
        # ... other existing actions
    ]


# Create a comprehensive admin dashboard view
class TeamBuildingDashboard:
    """
    Additional admin dashboard information
    You can add this as a custom admin view
    """
    
    @staticmethod
    def get_dashboard_stats():
        """Get comprehensive team building statistics"""
        from django.db.models import Count, Q
        
        stats = {}
        
        # Stage statistics
        for stage in [1, 2, 3, 4]:
            teams = models.Team.objects.filter(team_building_stage=stage)
            
            stats[f'stage_{stage}'] = {
                'total_teams': teams.count(),
                'complete_teams': teams.annotate(
                    member_count=Count('requests', filter=Q(requests__status='A', requests__request_type='JOIN'))
                ).filter(member_count__gte=2).count(),
                'formation_enabled': TeamBuildingSettings.is_stage_formation_enabled(stage),
                'page_enabled': TeamBuildingSettings.is_stage_page_enabled(stage)
            }
        
        # Users without teams
        stats['users_without_teams'] = User.objects.exclude(
            team_requests__status='A',
            team_requests__request_type='JOIN'
        ).count()
        
        # Pending invitations
        stats['pending_invitations'] = models.TeamRequest.objects.filter(
            status='W',
            request_type='INVITE'
        ).count()
        
        return stats


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