from __future__ import annotations

from typing import Iterable, Set
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from apps.project.models import ProjectAllocation
from apps.project.services import invalidate_attractiveness


def _extract_ids(priority) -> Set[str]:
    """
    Normalize priority JSON -> set[str(project_id)]
    Handles None/empty values, ensures consistent string typing for cache keys.
    """
    if not isinstance(priority, dict):
        return set()
    return {str(v) for v in priority.values() if v}


@receiver(pre_save, sender=ProjectAllocation)
def _pa_pre_save(sender, instance: ProjectAllocation, **kwargs):
    """
    Before saving an existing allocation, load the old priority set so we can
    invalidate both old and new keys after save.
    """
    if instance.pk:
        try:
            old = sender.objects.only("priority").get(pk=instance.pk)
            instance._old_priority_ids = _extract_ids(old.priority)
        except sender.DoesNotExist:
            instance._old_priority_ids = set()
    else:
        instance._old_priority_ids = set()


@receiver(post_save, sender=ProjectAllocation)
def _pa_post_save(sender, instance: ProjectAllocation, **kwargs):
    """
    After save, compute new set and invalidate union(old, new).
    This covers both create and update.
    """
    old_ids = getattr(instance, "_old_priority_ids", set())
    new_ids = _extract_ids(instance.priority)
    touched = old_ids.union(new_ids)
    if touched:
        invalidate_attractiveness(touched)


@receiver(post_delete, sender=ProjectAllocation)
def _pa_post_delete(sender, instance: ProjectAllocation, **kwargs):
    """
    On delete, invalidate whatever projects were referenced by this allocation.
    """
    ids = _extract_ids(instance.priority)
    if ids:
        invalidate_attractiveness(ids)
