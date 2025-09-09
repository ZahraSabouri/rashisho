from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.core.validators import MinLengthValidator

from apps.common.models import BaseModel

User = get_user_model()

COMMENT_STATUS_CHOICES = [
    ('PENDING', 'در انتظار تایید'),
    ('APPROVED', 'تایید شده'),
    ('REJECTED', 'رد شده'),
]

REACTION_TYPE_CHOICES = [
    ('LIKE', 'لایک'),
    ('DISLIKE', 'دیسلایک'),
]


class Comment(BaseModel):
    """
    Main comment model that can be attached to any model using GenericForeignKey.
    Supports threaded comments (replies), admin approval workflow, and user reactions.
    """
    # Content relation using Generic Foreign Key for flexibility
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE,
        verbose_name="نوع محتوا"
    )
    # object_id = models.PositiveIntegerField(verbose_name="شناسه آبجکت")
    object_id = models.CharField(max_length=36, verbose_name="شناسه آبجکت")
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # User and content
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_comments',
        verbose_name="کاربر"
    )
    content = models.TextField(
        validators=[MinLengthValidator(5)],
        verbose_name="متن نظر",
        help_text="حداقل 5 کاراکتر"
    )
    
    # Status and approval
    status = models.CharField(
        max_length=10,
        choices=COMMENT_STATUS_CHOICES,
        default='PENDING',
        verbose_name="وضعیت"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_user_comments',
        verbose_name="تایید شده توسط"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ تایید"
    )
    
    # Threaded comments support
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name="پاسخ به"
    )
    
    # Analytics fields
    likes_count = models.PositiveIntegerField(default=0, verbose_name="تعداد لایک")
    dislikes_count = models.PositiveIntegerField(default=0, verbose_name="تعداد دیسلایک")
    replies_count = models.PositiveIntegerField(default=0, verbose_name="تعداد پاسخ")
    
    class Meta(BaseModel.Meta):
        verbose_name = "نظر"
        verbose_name_plural = "نظرات"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.full_name if hasattr(self.user, 'full_name') else self.user.username} - {self.content[:50]}..."
    
    def get_absolute_url(self):
        """Get URL to the parent object this comment belongs to"""
        if hasattr(self.content_object, 'get_absolute_url'):
            return self.content_object.get_absolute_url()
        return None
    
    @property
    def is_approved(self):
        return self.status == 'APPROVED'
    
    @property
    def is_pending(self):
        return self.status == 'PENDING'
    
    def approve(self, approved_by_user):
        """Approve comment and update counters"""
        from django.utils import timezone
        self.status = 'APPROVED'
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()
        
        # Update parent comment replies count if this is a reply
        if self.parent:
            self.parent.replies_count = self.parent.replies.filter(status='APPROVED').count()
            self.parent.save(update_fields=['replies_count'])
    
    def reject(self, approved_by_user):
        """Reject comment"""
        from django.utils import timezone
        self.status = 'REJECTED'
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()


class CommentReaction(BaseModel):
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name="نظر"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comment_reactions',
        verbose_name="کاربر"
    )
    reaction_type = models.CharField(
        max_length=10,
        choices=REACTION_TYPE_CHOICES,
        verbose_name="نوع واکنش"
    )
    
    class Meta(BaseModel.Meta):
        verbose_name = "واکنش نظر"
        verbose_name_plural = "واکنش‌های نظرات"
        unique_together = ['comment', 'user']
        indexes = [
            models.Index(fields=['comment', 'reaction_type']),
        ]

    def __str__(self):
        return f"{self.user.full_name if hasattr(self.user, 'full_name') else self.user.username} - {self.get_reaction_type_display()} - {self.comment.id}"
    
    def save(self, *args, **kwargs):
        is_update = self.pk is not None and CommentReaction.objects.filter(pk=self.pk).exists()
        old_reaction_type = (
            CommentReaction.objects.get(pk=self.pk).reaction_type if is_update else None
        )

        super().save(*args, **kwargs)

        self.update_comment_counters(old_reaction_type)
    
    def delete(self, *args, **kwargs):
        reaction_type = self.reaction_type
        super().delete(*args, **kwargs)
        self.update_comment_counters(old_reaction_type=reaction_type, is_delete=True)
    
    def update_comment_counters(self, old_reaction_type=None, is_delete=False):
        comment = self.comment
        
        if is_delete:
            if old_reaction_type == 'LIKE':
                comment.likes_count = max(0, comment.likes_count - 1)
            elif old_reaction_type == 'DISLIKE':
                comment.dislikes_count = max(0, comment.dislikes_count - 1)
        elif old_reaction_type and old_reaction_type != self.reaction_type:
            if old_reaction_type == 'LIKE':
                comment.likes_count = max(0, comment.likes_count - 1)
            elif old_reaction_type == 'DISLIKE':
                comment.dislikes_count = max(0, comment.dislikes_count - 1)
            
            if self.reaction_type == 'LIKE':
                comment.likes_count += 1
            elif self.reaction_type == 'DISLIKE':
                comment.dislikes_count += 1
        elif not old_reaction_type:
            # New reaction
            if self.reaction_type == 'LIKE':
                comment.likes_count += 1
            elif self.reaction_type == 'DISLIKE':
                comment.dislikes_count += 1
        
        comment.save(update_fields=['likes_count', 'dislikes_count'])


class CommentModerationLog(BaseModel):
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name='moderation_logs',
        verbose_name="نظر"
    )
    moderator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comment_moderations',
        verbose_name="مدیر"
    )
    action = models.CharField(
        max_length=20,
        choices=[
            ('APPROVED', 'تایید'),
            ('REJECTED', 'رد'),
            ('DELETED', 'حذف'),
            ('EDITED', 'ویرایش'),
        ],
        verbose_name="عملیات"
    )
    reason = models.TextField(
        blank=True,
        verbose_name="دلیل",
        help_text="دلیل انجام این عملیات"
    )
    previous_status = models.CharField(max_length=10, choices=COMMENT_STATUS_CHOICES)
    new_status = models.CharField(max_length=10, choices=COMMENT_STATUS_CHOICES)

    
    class Meta(BaseModel.Meta):
        verbose_name = "لاگ مدیریت نظر"
        verbose_name_plural = "لاگ‌های مدیریت نظرات"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.moderator.full_name if hasattr(self.moderator, 'full_name') else self.moderator.username} - {self.get_action_display()}"