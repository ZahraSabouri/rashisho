from django.core.management.base import BaseCommand
from apps.project.models import ProjectAllocation, ProjectSelection, Project  # <— added Project import


class Command(BaseCommand):
    help = 'Migrate existing priority JSONB data to ProjectSelection table'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        allocations = ProjectAllocation.objects.all()
        migrated_count = 0
        error_count = 0

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No data will be actually migrated')
            )

        for allocation in allocations:
            try:
                if dry_run:
                    self.stdout.write(f"Would migrate: {allocation.user.full_name}")
                    for priority_str, project_id in allocation.priority.items():
                        if project_id:
                            exists = Project.objects.filter(id=project_id).exists()  # <— NEW
                            mark = "OK" if exists else "MISSING"                  # <— NEW
                            self.stdout.write(f"  Priority {priority_str}: {project_id} [{mark}]")
                else:
                    # Delete existing selections for this user
                    ProjectSelection.objects.filter(user=allocation.user).delete()

                    # Create new selections
                    for priority_str, project_id in allocation.priority.items():
                        if not project_id:
                            continue
                        # —— NEW: verify FK before insert to avoid DB errors
                        if not Project.objects.filter(id=project_id).exists():
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Skipping missing project {project_id} "
                                    f"(user={allocation.user_id}, priority={priority_str})"
                                )
                            )
                            error_count += 1
                            continue

                        try:
                            ProjectSelection.objects.create(
                                user=allocation.user,
                                project_id=project_id,
                                priority=int(priority_str)
                            )
                        except (ValueError, TypeError) as e:
                            self.stdout.write(self.style.ERROR(f"Error creating selection: {e}"))
                            error_count += 1
                            continue

                migrated_count += 1

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Error processing allocation {allocation.id}: {e}")
                )

        if not dry_run:
            total_selections = ProjectSelection.objects.count()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Migration completed!\n'
                    f'Processed: {migrated_count} allocations\n'
                    f'Errors/Skipped: {error_count}\n'
                    f'Total selections created: {total_selections}'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f'Would process: {migrated_count} allocations'))
