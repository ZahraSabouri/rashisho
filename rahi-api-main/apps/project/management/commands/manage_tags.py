"""
Usage examples:
python manage.py manage_tags --create-bulk "python" "django" "react" "machine-learning"
python manage.py manage_tags --cleanup-unused
python manage.py manage_tags --show-stats
python manage.py manage_tags --clear-cache
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from apps.project import models
import sys


class Command(BaseCommand):
    help = '''
    مدیریت تگ‌های پروژه
    
    عملیات موجود:
    - ایجاد تگ‌های متعدد
    - حذف تگ‌های استفاده نشده
    - نمایش آمار تگ‌ها
    - پاک کردن کش
    
    مثال‌ها:
    python manage.py manage_tags --create-bulk "python" "django" "react"
    python manage.py manage_tags --cleanup-unused
    python manage.py manage_tags --show-stats
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-bulk',
            nargs='+',
            help='ایجاد تگ‌های متعدد از نام‌های داده شده',
            metavar='TAG_NAME'
        )
        
        parser.add_argument(
            '--cleanup-unused',
            action='store_true',
            help='حذف تگ‌هایی که در هیچ پروژه‌ای استفاده نشده‌اند',
        )
        
        parser.add_argument(
            '--show-stats',
            action='store_true',
            help='نمایش آمار استفاده از تگ‌ها',
        )
        
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='پاک کردن کش‌های مرتبط با تگ‌ها',
        )
        
        parser.add_argument(
            '--export-tags',
            type=str,
            help='خروجی گرفتن از تگ‌ها به فایل مشخص شده',
            metavar='FILENAME'
        )
        
        parser.add_argument(
            '--find-similar',
            type=str,
            help='پیدا کردن تگ‌های مشابه برای تگ مشخص شده',
            metavar='TAG_NAME'
        )

    def handle(self, *args, **options):
        """Main command handler"""
        
        # Check if at least one option is provided
        if not any([
            options.get('create_bulk'),
            options.get('cleanup_unused'),
            options.get('show_stats'),
            options.get('clear_cache'),
            options.get('export_tags'),
            options.get('find_similar')
        ]):
            self.stdout.write(
                self.style.ERROR('حداقل یک عملیات را انتخاب کنید. --help برای کمک')
            )
            return
        
        if options['create_bulk']:
            self.handle_bulk_create(options['create_bulk'])
            
        if options['cleanup_unused']:
            self.handle_cleanup_unused()
            
        if options['show_stats']:
            self.handle_show_stats()
            
        if options['clear_cache']:
            self.handle_clear_cache()
            
        if options['export_tags']:
            self.handle_export_tags(options['export_tags'])
            
        if options['find_similar']:
            self.handle_find_similar(options['find_similar'])

    def handle_bulk_create(self, tag_names):
        """Create multiple tags from provided names"""
        self.stdout.write("در حال ایجاد تگ‌ها...")
        
        created_tags = []
        existing_tags = []
        invalid_tags = []
        
        for name in tag_names:
            # Clean the name
            clean_name = name.strip().lower()
            
            if len(clean_name) < 2:
                invalid_tags.append(name)
                continue
                
            if models.Tag.objects.filter(name=clean_name).exists():
                existing_tags.append(clean_name)
                continue
            
            try:
                tag = models.Tag.objects.create(
                    name=clean_name,
                    description=f'Auto-created tag: {clean_name}'
                )
                created_tags.append(tag)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'خطا در ایجاد تگ "{name}": {str(e)}')
                )
        
        # Show results
        if created_tags:
            self.stdout.write(
                self.style.SUCCESS(f'✅ {len(created_tags)} تگ جدید ایجاد شد:')
            )
            for tag in created_tags:
                self.stdout.write(f'   • {tag.name}')
        
        if existing_tags:
            self.stdout.write(
                self.style.WARNING(f'⚠️  {len(existing_tags)} تگ از قبل وجود داشت:')
            )
            for name in existing_tags:
                self.stdout.write(f'   • {name}')
                
        if invalid_tags:
            self.stdout.write(
                self.style.ERROR(f'❌ {len(invalid_tags)} نام نامعتبر:')
            )
            for name in invalid_tags:
                self.stdout.write(f'   • {name} (کمتر از 2 کاراکتر)')

    def handle_cleanup_unused(self):
        """Remove tags that are not used by any project"""
        self.stdout.write("در حال جستجوی تگ‌های استفاده نشده...")
        
        unused_tags = models.Tag.objects.annotate(
            project_count=Count('projects')
        ).filter(project_count=0)
        
        count = unused_tags.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✅ تگ استفاده نشده‌ای یافت نشد.'))
            return
        
        # Show which tags will be deleted
        self.stdout.write(f'🔍 {count} تگ استفاده نشده یافت شد:')
        for tag in unused_tags:
            self.stdout.write(f'   • {tag.name} (ایجاد شده: {tag.created_at.strftime("%Y-%m-%d")})')
        
        self.stdout.write('')
        confirm = input('آیا مطمئن هستید که می‌خواهید این تگ‌ها را حذف کنید؟ (y/N): ')
        
        if confirm.lower() in ['y', 'yes', 'بله']:
            deleted_count, details = unused_tags.delete()
            self.stdout.write(
                self.style.SUCCESS(f'✅ {deleted_count} تگ استفاده نشده حذف شد.')
            )
            
            # Clear cache after deletion
            cache.delete('popular_tags')
            
        else:
            self.stdout.write(self.style.WARNING('❌ عملیات لغو شد.'))

    def handle_show_stats(self):
        """Show comprehensive tag usage statistics"""
        self.stdout.write(self.style.HTTP_INFO("📊 آمار تگ‌های سیستم"))
        self.stdout.write("=" * 50)
        
        # Basic counts
        total_tags = models.Tag.objects.count()
        used_tags = models.Tag.objects.filter(projects__isnull=False).distinct().count()
        unused_tags = total_tags - used_tags
        
        self.stdout.write(f'📋 کل تگ‌ها: {total_tags}')
        self.stdout.write(f'✅ تگ‌های استفاده شده: {used_tags}')
        self.stdout.write(f'❌ تگ‌های استفاده نشده: {unused_tags}')
        
        if total_tags > 0:
            usage_percentage = (used_tags / total_tags) * 100
            self.stdout.write(f'📈 درصد استفاده: {usage_percentage:.1f}%')
        
        self.stdout.write('')
        
        # Most popular tags
        self.stdout.write("🏆 محبوب‌ترین تگ‌ها:")
        self.stdout.write("-" * 30)
        
        popular_tags = models.Tag.objects.annotate(
            total_projects=Count('projects'),
            visible_projects=Count('projects', filter=Q(projects__visible=True))
        ).filter(total_projects__gt=0).order_by('-total_projects')[:10]
        
        if popular_tags.exists():
            for i, tag in enumerate(popular_tags, 1):
                self.stdout.write(
                    f'{i:2d}. {tag.name:<20} '
                    f'({tag.visible_projects}/{tag.total_projects} پروژه)'
                )
        else:
            self.stdout.write('   هیچ تگی در پروژه‌ها استفاده نشده')
        
        # Project statistics
        self.stdout.write('')
        self.stdout.write("📚 آمار تگ‌گذاری پروژه‌ها:")
        self.stdout.write("-" * 30)
        
        total_projects = models.Project.objects.count()
        projects_with_tags = models.Project.objects.filter(tags__isnull=False).distinct().count()
        projects_without_tags = total_projects - projects_with_tags
        
        self.stdout.write(f'📁 کل پروژه‌ها: {total_projects}')
        self.stdout.write(f'🏷️  پروژه‌های دارای تگ: {projects_with_tags}')
        self.stdout.write(f'🚫 پروژه‌های بدون تگ: {projects_without_tags}')
        
        if total_projects > 0:
            tagging_percentage = (projects_with_tags / total_projects) * 100
            self.stdout.write(f'📊 درصد تگ‌گذاری: {tagging_percentage:.1f}%')
        
        # Average tags per project
        if projects_with_tags > 0:
            total_tag_relationships = models.Project.tags.through.objects.count()
            avg_tags = total_tag_relationships / projects_with_tags
            self.stdout.write(f'📏 میانگین تگ در هر پروژه: {avg_tags:.1f}')
        
        # Recent tag activity
        self.stdout.write('')
        self.stdout.write("🕒 فعالیت اخیر:")
        self.stdout.write("-" * 30)
        
        recent_tags = models.Tag.objects.order_by('-created_at')[:5]
        if recent_tags.exists():
            self.stdout.write('آخرین تگ‌های ایجاد شده:')
            for tag in recent_tags:
                self.stdout.write(f'   • {tag.name} ({tag.created_at.strftime("%Y-%m-%d")})')
        
        # Projects needing tags
        if projects_without_tags > 0:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING("⚠️  توصیه: پروژه‌های زیر تگ ندارند:"))
            untagged_projects = models.Project.objects.filter(
                tags__isnull=True, visible=True
            )[:5]
            
            for project in untagged_projects:
                self.stdout.write(f'   • {project.title}')
            
            if projects_without_tags > 5:
                self.stdout.write(f'   ... و {projects_without_tags - 5} پروژه دیگر')

    def handle_clear_cache(self):
        """Clear tag-related caches"""
        self.stdout.write("در حال پاک کردن کش‌های مرتبط با تگ‌ها...")
        
        # Clear specific cache keys
        cache_keys = [
            'popular_tags',
        ]
        
        # Clear related projects cache for all projects
        project_ids = models.Project.objects.values_list('id', flat=True)
        for project_id in project_ids:
            cache_keys.append(f'related_projects_{project_id}')
        
        # Clear the caches
        cache.delete_many(cache_keys)
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ {len(cache_keys)} کش پاک شد.')
        )

    def handle_export_tags(self, filename):
        """Export tags to a file"""
        try:
            tags = models.Tag.objects.annotate(
                project_count=Count('projects')
            ).order_by('name')
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write('نام تگ,توضیحات,تعداد پروژه‌ها,تاریخ ایجاد\n')
                for tag in tags:
                    f.write(f'"{tag.name}","{tag.description or ""}",{tag.project_count},{tag.created_at.strftime("%Y-%m-%d")}\n')
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ {tags.count()} تگ به فایل {filename} صادر شد.')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ خطا در صادر کردن: {str(e)}')
            )

    def handle_find_similar(self, tag_name):
        """Find tags similar to the given tag name"""
        try:
            tag = models.Tag.objects.get(name__iexact=tag_name)
        except models.Tag.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ تگ "{tag_name}" یافت نشد.')
            )
            return
        
        self.stdout.write(f'🔍 جستجوی تگ‌های مشابه "{tag.name}":')
        self.stdout.write("-" * 40)
        
        # Find tags that appear in projects with this tag
        projects_with_tag = models.Project.objects.filter(tags=tag)
        
        similar_tags = models.Tag.objects.filter(
            projects__in=projects_with_tag
        ).exclude(
            id=tag.id
        ).annotate(
            co_occurrence=Count('projects', filter=Q(projects__in=projects_with_tag)),
            total_usage=Count('projects')
        ).filter(
            co_occurrence__gt=0
        ).order_by('-co_occurrence')
        
        if similar_tags.exists():
            self.stdout.write('تگ‌های مرتبط (بر اساس هم‌رخدادی در پروژه‌ها):')
            for related_tag in similar_tags[:10]:
                percentage = (related_tag.co_occurrence / projects_with_tag.count()) * 100
                self.stdout.write(
                    f'   • {related_tag.name:<20} '
                    f'({related_tag.co_occurrence}/{projects_with_tag.count()} پروژه - {percentage:.1f}%)'
                )
        else:
            self.stdout.write('هیچ تگ مرتبطی یافت نشد.')
        
        # Show projects using this tag
        self.stdout.write('')
        self.stdout.write(f'پروژه‌های استفاده‌کننده از "{tag.name}":')
        for project in projects_with_tag[:5]:
            self.stdout.write(f'   • {project.title}')
        
        if projects_with_tag.count() > 5:
            self.stdout.write(f'   ... و {projects_with_tag.count() - 5} پروژه دیگر')