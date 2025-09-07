from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType

from apps.comments.models import Comment, CommentReaction
from apps.comments.services import CommentService


@receiver(post_save, sender=Comment)
def comment_post_save(sender, instance, created, **kwargs):
    """
    Handle actions after a comment is saved.
    Invalidates cache and triggers notifications.
    """
    # Invalidate cache for the related object
    content_type_str = f"{instance.content_type.app_label}.{instance.content_type.model}"
    CommentService.invalidate_comments_cache(content_type_str, instance.object_id)
    
    # If this is a newly created comment
    if created:
        # Update parent comment reply count if this is a reply
        if instance.parent:
            # This is already handled in the service, but keeping for safety
            instance.parent.replies_count = instance.parent.replies.filter(
                status='APPROVED'
            ).count()
            instance.parent.save(update_fields=['replies_count'])
        
        # Trigger notification service (placeholder for future implementation)
        try:
            from apps.comments.services import CommentNotificationService
            CommentNotificationService.notify_comment_created(instance)
        except ImportError:
            pass
    
    # If comment status changed to approved, update parent reply count
    if hasattr(instance, '_previous_status'):
        if instance._previous_status != 'APPROVED' and instance.status == 'APPROVED':
            if instance.parent:
                instance.parent.replies_count = instance.parent.replies.filter(
                    status='APPROVED'
                ).count()
                instance.parent.save(update_fields=['replies_count'])
            
            # Trigger approval notification
            try:
                from apps.comments.services import CommentNotificationService
                CommentNotificationService.notify_comment_approved(instance)
            except ImportError:
                pass


@receiver(pre_delete, sender=Comment)
def comment_pre_delete(sender, instance, **kwargs):
    """
    Handle actions before a comment is deleted.
    Updates parent reply counts and prepares for cache invalidation.
    """
    # Store information for post-delete processing
    instance._content_type_str = f"{instance.content_type.app_label}.{instance.content_type.model}"
    instance._object_id = instance.object_id
    instance._parent_id = instance.parent_id if instance.parent else None


@receiver(post_delete, sender=Comment)
def comment_post_delete(sender, instance, **kwargs):
    """
    Handle actions after a comment is deleted.
    Updates parent reply counts and invalidates cache.
    """
    # Invalidate cache
    if hasattr(instance, '_content_type_str') and hasattr(instance, '_object_id'):
        CommentService.invalidate_comments_cache(instance._content_type_str, instance._object_id)
    
    # Update parent reply count if this was a reply
    if hasattr(instance, '_parent_id') and instance._parent_id:
        try:
            parent = Comment.objects.get(id=instance._parent_id)
            parent.replies_count = parent.replies.filter(status='APPROVED').count()
            parent.save(update_fields=['replies_count'])
        except Comment.DoesNotExist:
            pass


@receiver(post_save, sender=CommentReaction)
def reaction_post_save(sender, instance, created, **kwargs):
    """
    Handle actions after a reaction is saved.
    The counter updates are already handled in the model's save method.
    """
    # Invalidate cache for the related comment's object
    content_type_str = f"{instance.comment.content_type.app_label}.{instance.comment.content_type.model}"
    CommentService.invalidate_comments_cache(content_type_str, instance.comment.object_id)


@receiver(post_delete, sender=CommentReaction)
def reaction_post_delete(sender, instance, **kwargs):
    """
    Handle actions after a reaction is deleted.
    The counter updates are already handled in the model's delete method.
    """
    # Invalidate cache for the related comment's object
    content_type_str = f"{instance.comment.content_type.app_label}.{instance.comment.content_type.model}"
    CommentService.invalidate_comments_cache(content_type_str, instance.comment.object_id)


# Store previous status for comparison in post_save
@receiver(post_save, sender=Comment)
def store_previous_status(sender, instance, **kwargs):
    """Store the previous status for comparison in signals."""
    try:
        previous = Comment.objects.get(pk=instance.pk)
        instance._previous_status = previous.status
    except Comment.DoesNotExist:
        instance._previous_status = None