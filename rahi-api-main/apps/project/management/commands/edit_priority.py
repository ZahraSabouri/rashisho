from django.core.management.base import BaseCommand

from apps.project.models import ProjectAllocation


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        allocations = ProjectAllocation.objects.all()

        for item in allocations:
            priority = item.priority
            for key, value in priority.items():
                if value == "nan":
                    item.priority[key] = ""
            item.save()

        print("Don successfully...")
