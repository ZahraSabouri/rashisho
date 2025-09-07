import logging
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q
from django.core.cache import cache

from apps.project.models import Project

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage project activation status - bulk operations and reporting'

    def add_arguments(self, parser):
        # Action arguments
        parser.add_argument(
            '--activate-all',
            action='store_true',
            help='فعال کردن همه پروژه‌ها'
        )
        
        parser.add_argument(
            '--deactivate-all',
            action='store_true', 
            help='غیرفعال کردن همه پروژه‌ها'
        )
        
        parser.add_argument(
            '--activate-projects',
            nargs='+',
            help='فعال کردن پروژه‌های خاص (با استفاده از ID)'
        )
        
        parser.add_argument(
            '--deactivate-projects',
            nargs='+',
            help='غیرفعال کردن پروژه‌های خاص (با استفاده از ID)'
        )
        
        parser.add_argument(
            '--show-stats',
            action='store_true',
            help='نمایش آمار وضعیت پروژه‌ها'
        )
        
        parser.add_argument(
            '--list-inactive',
            action='store_true',
            help='نمایش لیست پروژه‌های غیرفعال'
        )
        
        parser.add_argument(
            '--list-hidden',
            action='store_true',
            help='نمایش لیست پروژه‌های مخفی'
        )
        
        parser.add_argument(
            '--cleanup-orphaned',
            action='store_true',
            help='پاکسازی پروژه‌های بدون تخصیص (اختیاری)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='نمایش تغییرات بدون اعمال آنها'
        )
        
        parser.add_argument(
            '--reason',
            type=str,
            default='',
            help='دلیل تغییر وضعیت'
        )

    def handle(self, *args, **options):
        try:
            if options['show_stats']:
                self.show_project_stats()
            
            elif options['list_inactive']:
                self.list_inactive_projects()
            
            elif options['list_hidden']:
                self.list_hidden_projects()
            
            elif options['activate_all']:
                self.activate_all_projects(options['dry_run'], options['reason'])
            
            elif options['deactivate_all']:
                self.deactivate_all_projects(options['dry_run'], options['reason'])
            
            elif options['activate_projects']:
                self.activate_specific_projects(options['activate_projects'], options['dry_run'], options['reason'])
            
            elif options['deactivate_projects']:
                self.deactivate_specific_projects(options['deactivate_projects'], options['dry_run'], options['reason'])
            
            elif options['cleanup_orphaned']:
                self.cleanup_orphaned_projects(options['dry_run'])
            
            else:
                self.print_help('manage.py', 'manage_project_status')
                
        except Exception as e:
            logger.error(f"Command execution error: {str(e)}")
            raise CommandError(f"خطا در اجرای دستور: {str(e)}")

    def show_project_stats(self):
        """Show project status statistics"""
        stats = Project.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            inactive=Count('id', filter=Q(is_active=False)),
            visible=Count('id', filter=Q(visible=True)),
            hidden=Count('id', filter=Q(visible=False)),
            selectable=Count('id', filter=Q(is_active=True, visible=True))
        )
        
        self.stdout.write(
            self.style.SUCCESS("📊 آمار وضعیت پروژه‌ها:")
        )
        
        self.stdout.write(f"• کل پروژه‌ها: {stats['total']}")
        self.stdout.write(f"• فعال: {stats['active']} ({self._percentage(stats['active'], stats['total'])}%)")
        self.stdout.write(f"• غیرفعال: {stats['inactive']} ({self._percentage(stats['inactive'], stats['total'])}%)")
        self.stdout.write(f"• قابل مشاهده: {stats['visible']} ({self._percentage(stats['visible'], stats['total'])}%)")
        self.stdout.write(f"• مخفی: {stats['hidden']} ({self._percentage(stats['hidden'], stats['total'])}%)")
        self.stdout.write(f"• قابل انتخاب: {stats['selectable']} ({self._percentage(stats['selectable'], stats['total'])}%)")
        
        # Additional insights
        self.stdout.write("\n🔍 تحلیل بیشتر:")
        
        # Projects with no allocations
        no_allocations = Project.objects.annotate(
            allocation_count=Count('allocations')
        ).filter(allocation_count=0).count()
        
        self.stdout.write(f"• پروژه‌های بدون تخصیص: {no_allocations}")
        
        # Projects by company
        company_stats = Project.objects.values('company').annotate(
            count=Count('id'),
            active_count=Count('id', filter=Q(is_active=True))
        ).order_by('-count')[:5]
        
        if company_stats:
            self.stdout.write("\n🏢 برترین شرکت‌ها:")
            for stat in company_stats:
                self.stdout.write(
                    f"  - {stat['company']}: {stat['count']} پروژه "
                    f"({stat['active_count']} فعال)"
                )

    def list_inactive_projects(self):
        """List all inactive projects"""
        inactive_projects = Project.objects.filter(is_active=False).select_related()
        
        if not inactive_projects.exists():
            self.stdout.write(
                self.style.SUCCESS("✅ همه پروژه‌ها فعال هستند!")
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f"⚠️ پروژه‌های غیرفعال ({inactive_projects.count()}):")
        )
        
        for project in inactive_projects:
            allocations_count = project.allocations.count()
            self.stdout.write(
                f"• {project.title} (ID: {project.id}) - "
                f"شرکت: {project.company} - "
                f"تخصیص‌ها: {allocations_count}"
            )

    def list_hidden_projects(self):
        """List all hidden projects"""
        hidden_projects = Project.objects.filter(visible=False).select_related()
        
        if not hidden_projects.exists():
            self.stdout.write(
                self.style.SUCCESS("✅ همه پروژه‌ها قابل مشاهده هستند!")
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f"👁️ پروژه‌های مخفی ({hidden_projects.count()}):")
        )
        
        for project in hidden_projects:
            status = "فعال" if project.is_active else "غیرفعال"
            self.stdout.write(
                f"• {project.title} (ID: {project.id}) - "
                f"شرکت: {project.company} - وضعیت: {status}"
            )

    def activate_all_projects(self, dry_run, reason):
        """Activate all projects"""
        inactive_projects = Project.objects.filter(is_active=False)
        count = inactive_projects.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ همه پروژه‌ها از قبل فعال هستند!")
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"🔍 حالت آزمایشی: {count} پروژه فعال خواهد شد")
            )
            return
        
        updated_count = inactive_projects.update(is_active=True)
        
        # Clear cache
        cache.clear()
        
        # Log the operation
        logger.info(f"Bulk activation: {updated_count} projects activated. Reason: {reason}")
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ {updated_count} پروژه فعال شد")
        )

    def deactivate_all_projects(self, dry_run, reason):
        """Deactivate all projects"""
        active_projects = Project.objects.filter(is_active=True)
        count = active_projects.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("ℹ️ همه پروژه‌ها از قبل غیرفعال هستند!")
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"🔍 حالت آزمایشی: {count} پروژه غیرفعال خواهد شد")
            )
            return
        
        # Warning for mass deactivation
        self.stdout.write(
            self.style.ERROR(f"⚠️ هشدار: در حال غیرفعال کردن {count} پروژه")
        )
        
        updated_count = active_projects.update(is_active=False)
        
        # Clear cache
        cache.clear()
        
        # Log the operation
        logger.warning(f"Bulk deactivation: {updated_count} projects deactivated. Reason: {reason}")
        
        self.stdout.write(
            self.style.SUCCESS(f"⚠️ {updated_count} پروژه غیرفعال شد")
        )

    def activate_specific_projects(self, project_ids, dry_run, reason):
        """Activate specific projects by ID"""
        projects = Project.objects.filter(id__in=project_ids)
        
        if not projects.exists():
            raise CommandError("هیچ پروژه‌ای با شناسه‌های ارائه شده یافت نشد")
        
        inactive_projects = projects.filter(is_active=False)
        count = inactive_projects.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ همه پروژه‌های انتخابی از قبل فعال هستند!")
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"🔍 حالت آزمایشی: {count} پروژه فعال خواهد شد")
            )
            for project in inactive_projects:
                self.stdout.write(f"  - {project.title}")
            return
        
        updated_count = inactive_projects.update(is_active=True)
        
        # Clear cache
        cache.delete_many(['active_projects_list', 'project_status_stats'])
        
        # Log the operation
        logger.info(f"Specific activation: {updated_count} projects activated. Reason: {reason}")
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ {updated_count} پروژه فعال شد")
        )

    def deactivate_specific_projects(self, project_ids, dry_run, reason):
        """Deactivate specific projects by ID"""
        projects = Project.objects.filter(id__in=project_ids)
        
        if not projects.exists():
            raise CommandError("هیچ پروژه‌ای با شناسه‌های ارائه شده یافت نشد")
        
        active_projects = projects.filter(is_active=True)
        count = active_projects.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("ℹ️ همه پروژه‌های انتخابی از قبل غیرفعال هستند!")
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"🔍 حالت آزمایشی: {count} پروژه غیرفعال خواهد شد")
            )
            for project in active_projects:
                self.stdout.write(f"  - {project.title}")
            return
        
        updated_count = active_projects.update(is_active=False)
        
        # Clear cache
        cache.delete_many(['active_projects_list', 'project_status_stats'])
        
        # Log the operation
        logger.info(f"Specific deactivation: {updated_count} projects deactivated. Reason: {reason}")
        
        self.stdout.write(
            self.style.SUCCESS(f"⚠️ {updated_count} پروژه غیرفعال شد")
        )

    def cleanup_orphaned_projects(self, dry_run):
        """Clean up projects with no allocations (optional operation)"""
        orphaned_projects = Project.objects.annotate(
            allocation_count=Count('allocations')
        ).filter(allocation_count=0)
        
        count = orphaned_projects.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ پروژه بدون تخصیصی یافت نشد!")
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"🔍 حالت آزمایشی: {count} پروژه بدون تخصیص یافت شد")
            )
            for project in orphaned_projects[:10]:  # Show first 10
                self.stdout.write(f"  - {project.title} (شرکت: {project.company})")
            if count > 10:
                self.stdout.write(f"  ... و {count - 10} پروژه دیگر")
            return
        
        # This is a dangerous operation, ask for confirmation
        self.stdout.write(
            self.style.ERROR(f"⚠️ هشدار: {count} پروژه بدون تخصیص یافت شد")
        )
        self.stdout.write(
            "این پروژه‌ها ممکن است نیاز به بررسی داشته باشند، نه حذف خودکار."
        )

    def _percentage(self, part, total):
        """Calculate percentage safely"""
        if total == 0:
            return 0
        return round((part / total) * 100, 1)

# Usage examples:
# python manage.py manage_project_status --show-stats
# python manage.py manage_project_status --list-inactive
# python manage.py manage_project_status --activate-projects PROJECT_ID1 PROJECT_ID2 --reason "Re-enabling after review"
# python manage.py manage_project_status --deactivate-all --dry-run