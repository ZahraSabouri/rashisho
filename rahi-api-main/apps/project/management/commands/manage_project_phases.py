"""
Management command for project phase operations.
Usage examples:
  python manage.py manage_project_phases --list-phases
  python manage.py manage_project_phases --activate-all
  python manage.py manage_project_phases --set-phase ACTIVE --projects "id1,id2,id3"
  python manage.py manage_project_phases --auto-update
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.project.models import Project, ProjectPhase
from apps.project.services import (
    update_expired_project_phases, 
    activate_ready_projects,
    bulk_update_project_phases
)


class Command(BaseCommand):
    help = 'Manage project selection phases'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list-phases',
            action='store_true',
            help='نمایش وضعیت فاز همه پروژه‌ها'
        )
        
        parser.add_argument(
            '--set-phase',
            type=str,
            choices=['BEFORE', 'ACTIVE', 'FINISHED'],
            help='تنظیم فاز برای پروژه‌های مشخص شده'
        )
        
        parser.add_argument(
            '--projects',
            type=str,
            help='لیست ID پروژه‌ها جدا شده با کاما'
        )
        
        parser.add_argument(
            '--activate-all',
            action='store_true',
            help='فعال‌سازی فاز انتخاب برای همه پروژه‌ها'
        )
        
        parser.add_argument(
            '--finish-all',
            action='store_true',
            help='پایان فاز انتخاب برای همه پروژه‌ها'
        )
        
        parser.add_argument(
            '--reset-all',
            action='store_true',
            help='بازگشت همه پروژه‌ها به فاز قبل از انتخاب'
        )
        
        parser.add_argument(
            '--auto-update',
            action='store_true',
            help='به‌روزرسانی خودکار فازهای منقضی شده'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='نمایش تغییرات بدون اعمال آن‌ها'
        )

    def handle(self, *args, **options):
        if options['list_phases']:
            self.list_project_phases()
            
        elif options['set_phase'] and options['projects']:
            self.set_project_phases(
                options['set_phase'], 
                options['projects'], 
                options['dry_run']
            )
            
        elif options['activate_all']:
            self.activate_all_projects(options['dry_run'])
            
        elif options['finish_all']:
            self.finish_all_projects(options['dry_run'])
            
        elif options['reset_all']:
            self.reset_all_projects(options['dry_run'])
            
        elif options['auto_update']:
            self.auto_update_phases(options['dry_run'])
            
        else:
            self.stdout.write(
                self.style.WARNING('لطفاً یکی از گزینه‌ها را انتخاب کنید. --help برای راهنما')
            )

    def list_project_phases(self):
        """List all projects with their current phases"""
        projects = Project.objects.all().order_by('selection_phase', 'title')
        
        if not projects.exists():
            self.stdout.write(self.style.WARNING('هیچ پروژه‌ای یافت نشد!'))
            return
        
        # Group by phase
        phases = {}
        for project in projects:
            phase = project.current_phase
            if phase not in phases:
                phases[phase] = []
            phases[phase].append(project)
        
        for phase, projects_list in phases.items():
            phase_label = ProjectPhase(phase).label
            self.stdout.write(
                self.style.HTTP_INFO(f'\n📋 {phase_label} ({len(projects_list)} پروژه):')
            )
            
            for project in projects_list:
                auto_indicator = "🤖" if project.auto_phase_transition else "📝"
                attractiveness = project.selections.count() if hasattr(project, 'selections') else 0
                
                self.stdout.write(
                    f"  {auto_indicator} {project.title} (جذابیت: {attractiveness})"
                )
                
                if project.selection_start or project.selection_end:
                    start = project.selection_start.strftime("%Y/%m/%d %H:%M") if project.selection_start else "نامشخص"
                    end = project.selection_end.strftime("%Y/%m/%d %H:%M") if project.selection_end else "نامشخص"
                    self.stdout.write(f"     ⏰ {start} - {end}")

    def set_project_phases(self, new_phase, project_ids_str, dry_run):
        """Set specific projects to a new phase"""
        project_ids = [pid.strip() for pid in project_ids_str.split(',')]
        
        try:
            projects = Project.objects.filter(id__in=project_ids)
            found_count = projects.count()
            
            if found_count == 0:
                self.stdout.write(self.style.ERROR('هیچ پروژه‌ای با ID های داده شده یافت نشد!'))
                return
                
            if found_count != len(project_ids):
                self.stdout.write(
                    self.style.WARNING(f'تنها {found_count} از {len(project_ids)} پروژه یافت شد.')
                )
            
            phase_map = {
                'BEFORE': ProjectPhase.BEFORE_SELECTION,
                'ACTIVE': ProjectPhase.SELECTION_ACTIVE,
                'FINISHED': ProjectPhase.SELECTION_FINISHED
            }
            
            new_phase_value = phase_map[new_phase]
            
            if dry_run:
                self.stdout.write(self.style.WARNING('حالت آزمایشی - تغییرات اعمال نمی‌شود:'))
                for project in projects:
                    self.stdout.write(f"  {project.title}: {project.current_phase} → {new_phase_value}")
            else:
                # Update with current timestamp
                now = timezone.now()
                update_fields = ['selection_phase']
                
                for project in projects:
                    project.selection_phase = new_phase_value
                    if new_phase == 'ACTIVE' and not project.selection_start:
                        project.selection_start = now
                        update_fields.append('selection_start')
                    elif new_phase == 'FINISHED' and not project.selection_end:
                        project.selection_end = now
                        update_fields.append('selection_end')
                
                Project.objects.bulk_update(projects, list(set(update_fields)))
                
                self.stdout.write(
                    self.style.SUCCESS(f'{found_count} پروژه به فاز {ProjectPhase(new_phase_value).label} تغییر یافت.')
                )
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'خطا: {str(e)}'))

    def activate_all_projects(self, dry_run):
        """Activate selection phase for all projects"""
        projects = Project.objects.all()
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'حالت آزمایشی: {projects.count()} پروژه فعال خواهد شد'))
        else:
            updated = projects.update(
                selection_phase=ProjectPhase.SELECTION_ACTIVE,
                selection_start=timezone.now()
            )
            self.stdout.write(
                self.style.SUCCESS(f'{updated} پروژه به فاز انتخاب فعال تغییر یافت.')
            )

    def finish_all_projects(self, dry_run):
        """Finish selection phase for all projects"""
        projects = Project.objects.all()
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'حالت آزمایشی: {projects.count()} پروژه به پایان می‌رسد'))
        else:
            updated = projects.update(
                selection_phase=ProjectPhase.SELECTION_FINISHED,
                selection_end=timezone.now()
            )
            self.stdout.write(
                self.style.SUCCESS(f'{updated} پروژه به فاز پایان انتخاب تغییر یافت.')
            )

    def reset_all_projects(self, dry_run):
        """Reset all projects to before selection phase"""
        projects = Project.objects.all()
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'حالت آزمایشی: {projects.count()} پروژه بازنشانی خواهد شد'))
        else:
            updated = projects.update(selection_phase=ProjectPhase.BEFORE_SELECTION)
            self.stdout.write(
                self.style.SUCCESS(f'{updated} پروژه به فاز قبل از انتخاب بازگردانده شد.')
            )

    def auto_update_phases(self, dry_run):
        """Auto-update phases based on dates"""
        if dry_run:
            self.stdout.write(self.style.WARNING('حالت آزمایشی - به‌روزرسانی خودکار فازها:'))
            
            # Check what would be updated
            now = timezone.now()
            
            ready_projects = Project.objects.filter(
                auto_phase_transition=True,
                selection_phase=ProjectPhase.BEFORE_SELECTION,
                selection_start__lte=now,
                selection_end__gt=now
            )
            self.stdout.write(f"  {ready_projects.count()} پروژه آماده فعال‌سازی")
            
            expired_projects = Project.objects.filter(
                auto_phase_transition=True,
                selection_phase=ProjectPhase.SELECTION_ACTIVE,
                selection_end__lt=now
            )
            self.stdout.write(f"  {expired_projects.count()} پروژه آماده پایان")
            
        else:
            activated = activate_ready_projects()
            finished = update_expired_project_phases()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'به‌روزرسانی خودکار انجام شد:\n'
                    f'  فعال شده: {activated} پروژه\n'
                    f'  پایان یافته: {finished} پروژه'
                )
            )