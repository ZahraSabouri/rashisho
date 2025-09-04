"""
Periodic task to automatically update project phases based on dates.
Run this command in a cron job every 5-15 minutes.

Example cron job (every 10 minutes):
*/10 * * * * cd /path/to/project && python manage.py update_project_phases

Or use Django-crontab:
CRONJOBS = [
    ('*/10 * * * *', 'django.core.management.call_command', ['update_project_phases']),
]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.project.services import update_expired_project_phases, activate_ready_projects
from apps.project.models import Project, ProjectPhase
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update project phases automatically based on dates (for cron jobs)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='نمایش جزئیات بیشتر'
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        now = timezone.now()
        
        if verbose:
            self.stdout.write(f'🕒 شروع به‌روزرسانی خودکار فازها در {now.strftime("%Y-%m-%d %H:%M:%S")}')
        
        try:
            # Activate projects that should start selection
            activated = activate_ready_projects()
            
            # Finish projects that passed their end date  
            finished = update_expired_project_phases()
            
            total_changes = activated + finished
            
            if total_changes > 0:
                message = f'✅ به‌روزرسانی انجام شد: {activated} فعال، {finished} پایان یافت'
                self.stdout.write(self.style.SUCCESS(message))
                logger.info(f'Phase update: {activated} activated, {finished} finished')
                
            elif verbose:
                self.stdout.write('ℹ️ نیازی به به‌روزرسانی نبود')
                
        except Exception as e:
            error_msg = f'❌ خطا در به‌روزرسانی فازها: {str(e)}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            
        if verbose:
            # Show current phase statistics
            self.show_phase_statistics()

    def show_phase_statistics(self):
        """Show current phase distribution"""
        stats = {}
        
        for phase_choice in ProjectPhase.choices:
            count = Project.objects.filter(selection_phase=phase_choice[0]).count()
            stats[phase_choice[1]] = count
        
        self.stdout.write('\n📊 آمار فازهای فعلی:')
        for phase_name, count in stats.items():
            self.stdout.write(f'   {phase_name}: {count} پروژه')


# apps/project/management/commands/setup_phase_cron.py
"""
Helper command to set up automatic phase updates using django-crontab
Install: pip install django-crontab
Add to INSTALLED_APPS: 'django_crontab'
"""
from django.core.management.base import BaseCommand


class SetupPhaseCronCommand(BaseCommand):
    help = 'راهنمای تنظیم کرون جاب برای به‌روزرسانی خودکار فازها'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('📋 راهنمای تنظیم کرون جاب:'))
        self.stdout.write('')
        
        self.stdout.write('1️⃣ نصب django-crontab:')
        self.stdout.write('   pip install django-crontab')
        self.stdout.write('')
        
        self.stdout.write('2️⃣ اضافه کردن به INSTALLED_APPS:')
        self.stdout.write("   INSTALLED_APPS = [..., 'django_crontab', ...]")
        self.stdout.write('')
        
        self.stdout.write('3️⃣ اضافه کردن به settings.py:')
        self.stdout.write("""CRONJOBS = [
    # هر 10 دقیقه یکبار
    ('*/10 * * * *', 'django.core.management.call_command', ['update_project_phases']),
    
    # یا هر 5 دقیقه برای دقت بیشتر
    ('*/5 * * * *', 'django.core.management.call_command', ['update_project_phases']),
]""")
        self.stdout.write('')
        
        self.stdout.write('4️⃣ فعال‌سازی کرون جاب:')
        self.stdout.write('   python manage.py crontab add')
        self.stdout.write('')
        
        self.stdout.write('5️⃣ مشاهده کرون جاب‌های فعال:')
        self.stdout.write('   python manage.py crontab show')
        self.stdout.write('')
        
        self.stdout.write('6️⃣ حذف کرون جاب‌ها (در صورت نیاز):')
        self.stdout.write('   python manage.py crontab remove')
        self.stdout.write('')
        
        self.stdout.write('🔄 تست دستی:')
        self.stdout.write('   python manage.py update_project_phases --verbose')
        self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS('✅ پس از تنظیم، فازها به‌طور خودکار بر اساس تاریخ شروع و پایان به‌روزرسانی خواهند شد.'))