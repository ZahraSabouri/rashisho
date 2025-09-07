from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html, strip_tags
from django.utils.safestring import mark_safe
from django.utils import timezone

from apps.comments.models import Comment, CommentReaction, CommentModerationLog


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """
    Admin interface for Comment model with advanced filtering,
    bulk actions, and moderation capabilities.
    """
    list_display = [
        'id', 'content_preview', 'user_display', 'content_type_display',
        'status_display', 'likes_count', 'dislikes_count', 'replies_count',
        'created_at', 'approved_by'
    ]
    list_filter = [
        'status', 'content_type', 'created_at', 'approved_at',
        ('parent', admin.EmptyFieldListFilter)
    ]
    search_fields = [
        'content', 'user__username', 'user__first_name', 'user__last_name',
        'user__email'
    ]
    readonly_fields = [
        'id', 'content_type', 'object_id', 'created_at', 'updated_at',
        'likes_count', 'dislikes_count', 'replies_count', 'content_object_link'
    ]
    fields = [
        'id', 'content', 'user', 'status', 'content_type', 'object_id',
        'content_object_link', 'parent', 'likes_count', 'dislikes_count',
        'replies_count', 'approved_by', 'approved_at', 'created_at', 'updated_at'
    ]
    actions = ['approve_comments', 'reject_comments', 'reset_to_pending']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        """Optimize admin queryset with related objects"""
        return super().get_queryset(request).select_related(
            'user', 'content_type', 'parent', 'approved_by'
        ).annotate(
            reactions_count=Count('reactions')
        )
    
    def content_preview(self, obj):
        """Show truncated content with full content on hover"""
        content = strip_tags(obj.content)
        if len(content) > 100:
            preview = content[:97] + "..."
            return format_html(
                '<span title="{}">{}</span>',
                content,
                preview
            )
        return content
    content_preview.short_description = 'محتوای نظر'
    
    def user_display(self, obj):
        """Display user with link to admin page"""
        if obj.user:
            url = reverse('admin:account_user_change', args=[obj.user.pk])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.user.full_name if hasattr(obj.user, 'full_name') else obj.user.username
            )
        return '-'
    user_display.short_description = 'کاربر'
    
    def content_type_display(self, obj):
        """Display content type in Persian"""
        if obj.content_type:
            type_names = {
                'project': 'پروژه',
                'post': 'پست', 
                'article': 'مقاله',
            }
            return type_names.get(obj.content_type.model, obj.content_type.model)
        return '-'
    content_type_display.short_description = 'نوع محتوا'
    
    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            'PENDING': '#FFA500',  # Orange
            'APPROVED': '#28a745',  # Green
            'REJECTED': '#dc3545',  # Red
        }
        color = colors.get(obj.status, '#6c757d')
        status_text = obj.get_status_display()
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            status_text
        )
    status_display.short_description = 'وضعیت'
    
    def content_object_link(self, obj):
        """Show link to the content object"""
        if obj.content_object:
            try:
                # Try to get admin URL for the content object
                content_type = obj.content_type
                url = reverse(
                    f'admin:{content_type.app_label}_{content_type.model}_change',
                    args=[obj.object_id]
                )
                return format_html(
                    '<a href="{}" target="_blank">مشاهده {}</a>',
                    url,
                    content_type.model
                )
            except:
                return str(obj.content_object)
        return '-'
    content_object_link.short_description = 'لینک محتوا'
    
    # Bulk actions
    def approve_comments(self, request, queryset):
        """Bulk approve comments"""
        count = 0
        for comment in queryset.filter(status='PENDING'):
            comment.approve(request.user)
            
            # Log the action
            CommentModerationLog.objects.create(
                comment=comment,
                moderator=request.user,
                action='APPROVED',
                reason='تایید گروهی از پنل ادمین'
            )
            count += 1
        
        self.message_user(request, f'{count} نظر تایید شد.')
    approve_comments.short_description = 'تایید نظرات انتخاب شده'
    
    def reject_comments(self, request, queryset):
        """Bulk reject comments"""
        count = 0
        for comment in queryset.exclude(status='REJECTED'):
            comment.reject(request.user)
            
            # Log the action  
            CommentModerationLog.objects.create(
                comment=comment,
                moderator=request.user,
                action='REJECTED',
                reason='رد گروهی از پنل ادمین'
            )
            count += 1
        
        self.message_user(request, f'{count} نظر رد شد.')
    reject_comments.short_description = 'رد نظرات انتخاب شده'
    
    def reset_to_pending(self, request, queryset):
        """Reset comments to pending status"""
        count = queryset.exclude(status='PENDING').update(
            status='PENDING',
            approved_by=None,
            approved_at=None
        )
        self.message_user(request, f'{count} نظر به حالت در انتظار تغییر یافت.')
    reset_to_pending.short_description = 'تغییر به حالت در انتظار'


@admin.register(CommentReaction)
class CommentReactionAdmin(admin.ModelAdmin):
    """Admin interface for comment reactions"""
    list_display = ['id', 'comment_preview', 'user_display', 'reaction_type', 'created_at']
    list_filter = ['reaction_type', 'created_at']
    search_fields = [
        'comment__content', 'user__username', 'user__first_name', 'user__last_name'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('comment', 'user')
    
    def comment_preview(self, obj):
        """Show comment preview"""
        content = strip_tags(obj.comment.content)
        if len(content) > 50:
            return content[:47] + "..."
        return content
    comment_preview.short_description = 'نظر'
    
    def user_display(self, obj):
        """Display user name"""
        return obj.user.full_name if hasattr(obj.user, 'full_name') else obj.user.username
    user_display.short_description = 'کاربر'


@admin.register(CommentModerationLog)
class CommentModerationLogAdmin(admin.ModelAdmin):
    """Admin interface for comment moderation logs"""
    list_display = [
        'id', 'comment_preview', 'moderator_display', 'action',
        'reason_preview', 'created_at'
    ]
    list_filter = ['action', 'created_at', 'moderator']
    search_fields = [
        'comment__content', 'moderator__username', 'moderator__first_name',
        'moderator__last_name', 'reason'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('comment', 'moderator')
    
    def comment_preview(self, obj):
        """Show comment preview"""
        content = strip_tags(obj.comment.content)
        if len(content) > 50:
            return content[:47] + "..."
        return content
    comment_preview.short_description = 'نظر'
    
    def moderator_display(self, obj):
        """Display moderator name"""
        return obj.moderator.full_name if hasattr(obj.moderator, 'full_name') else obj.moderator.username
    moderator_display.short_description = 'مدیر'
    
    def reason_preview(self, obj):
        """Show reason preview"""
        if obj.reason:
            if len(obj.reason) > 50:
                return obj.reason[:47] + "..."
            return obj.reason
        return '-'
    reason_preview.short_description = 'دلیل'


# Register admin customizations
admin.site.index_template = 'admin/custom_index.html'  # Optional: custom admin index

# Add custom admin actions and filters
class CommentStatusFilter(admin.SimpleListFilter):
    """Custom filter for comment status with counts"""
    title = 'وضعیت نظر'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        # Get status counts
        pending_count = Comment.objects.filter(status='PENDING').count()
        approved_count = Comment.objects.filter(status='APPROVED').count() 
        rejected_count = Comment.objects.filter(status='REJECTED').count()
        
        return [
            ('PENDING', f'در انتظار ({pending_count})'),
            ('APPROVED', f'تایید شده ({approved_count})'),
            ('REJECTED', f'رد شده ({rejected_count})'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


# Replace the default status filter
CommentAdmin.list_filter = [
    CommentStatusFilter, 'content_type', 'created_at', 'approved_at',
    ('parent', admin.EmptyFieldListFilter)
]