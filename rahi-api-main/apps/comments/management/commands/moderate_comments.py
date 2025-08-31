from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.comments.models import Comment, CommentModerationLog
from apps.comments.services import CommentService

User = get_user_model()


class Command(BaseCommand):
    help = 'مدیریت گروهی نظرات - تایید، رد، یا پردازش نظرات در انتظار'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['approve', 'reject', 'list', 'stats'],
            required=True,
            help='عملیات مورد نظر: approve, reject, list, stats'
        )
        
        parser.add_argument(
            '--moderator-id',
            type=int,
            help='شناسه کاربر مدیر (برای approve و reject)'
        )
        
        parser.add_argument(
            '--comment-ids',
            type=str,
            help='شناسه‌های نظرات جدا شده با کاما (برای approve و reject)'
        )
        
        parser.add_argument(
            '--status',
            type=str,
            choices=['PENDING', 'APPROVED', 'REJECTED'],
            default='PENDING',
            help='وضعیت نظرات برای نمایش (برای list)'
        )
        
        parser.add_argument(
            '--reason',
            type=str,
            help='دلیل تغییر وضعیت'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='تعداد نظرات برای نمایش (برای list)'
        )
        
        parser.add_argument(
            '--auto-approve-old',
            action='store_true',
            help='تایید خودکار نظرات قدیمی (بیشتر از 7 روز) بدون گزارش'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        try:
            if action == 'list':
                self.list_comments(options)
            elif action == 'stats':
                self.show_stats(options)
            elif action in ['approve', 'reject']:
                self.moderate_comments(options)
            elif options['auto_approve_old']:
                self.auto_approve_old_comments(options)
                
        except Exception as e:
            raise CommandError(f'خطا در اجرای دستور: {str(e)}')

    def list_comments(self, options):
        """نمایش لیست نظرات"""
        status_filter = options['status']
        limit = options['limit']
        
        comments = Comment.objects.filter(status=status_filter).select_related(
            'user', 'content_type'
        ).order_by('-created_at')[:limit]
        
        self.stdout.write(
            self.style.SUCCESS(f'\n=== نظرات با وضعیت {status_filter} ===\n')
        )
        
        if not comments:
            self.stdout.write('هیچ نظری یافت نشد.')
            return
        
        for comment in comments:
            user_name = getattr(comment.user, 'full_name', comment.user.username)
            content_preview = comment.content[:100] + '...' if len(comment.content) > 100 else comment.content
            
            self.stdout.write(f'ID: {comment.id}')
            self.stdout.write(f'کاربر: {user_name}')
            self.stdout.write(f'محتوا: {content_preview}')
            self.stdout.write(f'نوع: {comment.content_type.model}')
            self.stdout.write(f'تاریخ: {comment.created_at.strftime("%Y-%m-%d %H:%M")}')
            self.stdout.write(f'لایک‌ها: {comment.likes_count} | دیسلایک‌ها: {comment.dislikes_count}')
            self.stdout.write('-' * 50)

    def show_stats(self, options):
        """نمایش آمار نظرات"""
        stats = CommentService.get_comment_statistics()
        
        self.stdout.write(self.style.SUCCESS('\n=== آمار کلی نظرات ===\n'))
        self.stdout.write(f'مجموع نظرات: {stats["total"]}')
        self.stdout.write(f'تایید شده: {stats["approved"]} ({stats["approval_rate"]}%)')
        self.stdout.write(f'در انتظار: {stats["pending"]} ({stats["pending_rate"]}%)')
        self.stdout.write(f'رد شده: {stats["rejected"]}')
        self.stdout.write(f'مجموع لایک‌ها: {stats["total_likes"]}')
        self.stdout.write(f'مجموع دیسلایک‌ها: {stats["total_dislikes"]}')
        self.stdout.write(f'مجموع پاسخ‌ها: {stats["total_replies"]}')

    def moderate_comments(self, options):
        """مدیریت نظرات (تایید/رد)"""
        action = options['action']
        moderator_id = options['moderator_id']
        comment_ids_str = options['comment_ids']
        reason = options.get('reason', '')
        
        if not moderator_id:
            raise CommandError('شناسه مدیر (--moderator-id) الزامی است')
        
        try:
            moderator = User.objects.get(id=moderator_id)
            if not (hasattr(moderator, 'role') and moderator.role == 0):
                raise CommandError('کاربر مشخص شده مدیر نیست')
        except User.DoesNotExist:
            raise CommandError('مدیر با شناسه مشخص شده یافت نشد')
        
        if comment_ids_str:
            # عملیات روی نظرات مشخص شده
            try:
                comment_ids = [int(id.strip()) for id in comment_ids_str.split(',')]
            except ValueError:
                raise CommandError('فرمت شناسه‌های نظر نامعتبر است')
            
            success_count = CommentService.bulk_moderate_comments(
                comment_ids, action, moderator, reason
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'{success_count} نظر با موفقیت {action} شدند'
                )
            )
        else:
            # عملیات روی همه نظرات در انتظار
            if action == 'approve':
                pending_comments = Comment.objects.filter(status='PENDING')
            else:
                raise CommandError('برای رد گروهی باید شناسه نظرات را مشخص کنید')
            
            comment_ids = list(pending_comments.values_list('id', flat=True))
            
            if not comment_ids:
                self.stdout.write('هیچ نظر در انتظاری یافت نشد')
                return
            
            # تأیید از کاربر
            confirm = input(f'آیا مطمئن هستید که می‌خواهید {len(comment_ids)} نظر را {action} کنید؟ (y/N): ')
            
            if confirm.lower() != 'y':
                self.stdout.write('عملیات لغو شد')
                return
            
            success_count = CommentService.bulk_moderate_comments(
                comment_ids, action, moderator, reason or f'{action} گروهی از طریق دستور مدیریتی'
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'{success_count} نظر با موفقیت {action} شدند'
                )
            )

    def auto_approve_old_comments(self, options):
        """تایید خودکار نظرات قدیمی"""
        from django.utils import timezone
        from datetime import timedelta
        
        moderator_id = options['moderator_id']
        
        if not moderator_id:
            # ایجاد کاربر سیستم برای عملیات خودکار
            moderator, created = User.objects.get_or_create(
                username='system_auto_moderator',
                defaults={
                    'email': 'system@rahisho.com',
                    'is_active': False,
                    'role': 0
                }
            )
        else:
            try:
                moderator = User.objects.get(id=moderator_id)
            except User.DoesNotExist:
                raise CommandError('مدیر یافت نشد')
        
        # نظرات قدیمی‌تر از 7 روز
        cutoff_date = timezone.now() - timedelta(days=7)
        old_pending_comments = Comment.objects.filter(
            status='PENDING',
            created_at__lt=cutoff_date
        )
        
        comment_ids = list(old_pending_comments.values_list('id', flat=True))
        
        if not comment_ids:
            self.stdout.write('نظر قدیمی در انتظاری یافت نشد')
            return
        
        self.stdout.write(f'یافت شد {len(comment_ids)} نظر قدیمی در انتظار تایید')
        
        success_count = CommentService.bulk_moderate_comments(
            comment_ids,
            'approve',
            moderator,
            'تایید خودکار نظرات قدیمی (بیشتر از 7 روز)'
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'{success_count} نظر قدیمی به صورت خودکار تایید شدند'
            )
        )


# apps/comments/management/commands/cleanup_comments.py
"""
Management command for cleaning up comment data.
Removes orphaned reactions, updates counters, and performs maintenance.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from apps.comments.models import Comment, CommentReaction


class Command(BaseCommand):
    help = 'پاکسازی و نگهداری داده‌های نظرات'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-counters',
            action='store_true',
            help='تصحیح شمارنده‌های لایک، دیسلایک و پاسخ‌ها'
        )
        
        parser.add_argument(
            '--remove-orphaned',
            action='store_true',
            help='حذف واکنش‌های بدون نظر'
        )
        
        parser.add_argument(
            '--update-reply-counts',
            action='store_true',
            help='به‌روزرسانی تعداد پاسخ‌ها'
        )
        
        parser.add_argument(
            '--all',
            action='store_true',
            help='اجرای همه عملیات پاکسازی'
        )

    def handle(self, *args, **options):
        if options['all']:
            options['fix_counters'] = True
            options['remove_orphaned'] = True
            options['update_reply_counts'] = True
        
        if options['fix_counters']:
            self.fix_counters()
        
        if options['remove_orphaned']:
            self.remove_orphaned_reactions()
        
        if options['update_reply_counts']:
            self.update_reply_counts()
        
        self.stdout.write(self.style.SUCCESS('پاکسازی با موفقیت انجام شد'))

    @transaction.atomic
    def fix_counters(self):
        """تصحیح شمارنده‌های لایک و دیسلایک"""
        self.stdout.write('تصحیح شمارنده‌های واکنش‌ها...')
        
        comments = Comment.objects.all()
        updated_count = 0
        
        for comment in comments:
            # محاسبه تعداد واقعی واکنش‌ها
            likes = comment.reactions.filter(reaction_type='LIKE').count()
            dislikes = comment.reactions.filter(reaction_type='DISLIKE').count()
            
            # بررسی نیاز به به‌روزرسانی
            if comment.likes_count != likes or comment.dislikes_count != dislikes:
                comment.likes_count = likes
                comment.dislikes_count = dislikes
                comment.save(update_fields=['likes_count', 'dislikes_count'])
                updated_count += 1
        
        self.stdout.write(f'تعداد {updated_count} نظر به‌روزرسانی شد')

    def remove_orphaned_reactions(self):
        """حذف واکنش‌های بدون نظر"""
        self.stdout.write('حذف واکنش‌های یتیم...')
        
        # یافتن واکنش‌هایی که نظر مربوطه حذف شده
        orphaned_count = CommentReaction.objects.filter(
            comment__isnull=True
        ).count()
        
        if orphaned_count > 0:
            CommentReaction.objects.filter(comment__isnull=True).delete()
            self.stdout.write(f'تعداد {orphaned_count} واکنش یتیم حذف شد')
        else:
            self.stdout.write('واکنش یتیمی یافت نشد')

    @transaction.atomic
    def update_reply_counts(self):
        """به‌روزرسانی تعداد پاسخ‌ها"""
        self.stdout.write('به‌روزرسانی تعداد پاسخ‌ها...')
        
        # تنها نظرات والد (بدون parent) را بررسی می‌کنیم
        parent_comments = Comment.objects.filter(parent__isnull=True)
        updated_count = 0
        
        for comment in parent_comments:
            actual_replies = comment.replies.filter(status='APPROVED').count()
            
            if comment.replies_count != actual_replies:
                comment.replies_count = actual_replies
                comment.save(update_fields=['replies_count'])
                updated_count += 1
        
        self.stdout.write(f'تعداد {updated_count} نظر والد به‌روزرسانی شد')


# apps/comments/management/commands/export_comments.py
"""
Management command for exporting comments data.
Allows exporting comments in various formats for backup or analysis.
"""
import csv
import json
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType

from apps.comments.models import Comment
from apps.comments.services import CommentExportService


class Command(BaseCommand):
    help = 'خروجی گرفتن از نظرات در فرمت‌های مختلف'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['csv', 'json'],
            default='csv',
            help='فرمت خروجی: csv یا json'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            help='مسیر فایل خروجی'
        )
        
        parser.add_argument(
            '--content-type',
            type=str,
            help='فیلتر بر اساس نوع محتوا (مثل project.project)'
        )
        
        parser.add_argument(
            '--object-id',
            type=int,
            help='شناسه آبجکت مشخص'
        )
        
        parser.add_argument(
            '--status',
            type=str,
            choices=['PENDING', 'APPROVED', 'REJECTED'],
            help='فیلتر بر اساس وضعیت'
        )
        
        parser.add_argument(
            '--include-content',
            action='store_true',
            help='شامل کردن محتوای کامل نظرات'
        )

    def handle(self, *args, **options):
        try:
            # ایجاد کوئری بر اساس فیلترها
            queryset = self.build_queryset(options)
            
            # تولید نام فایل اگر مشخص نشده
            output_file = options.get('output') or self.generate_filename(options['format'])
            
            # خروجی گرفتن
            if options['format'] == 'csv':
                self.export_csv(queryset, output_file, options['include_content'])
            else:
                self.export_json(queryset, output_file, options['include_content'])
                
            self.stdout.write(
                self.style.SUCCESS(f'خروجی با موفقیت در فایل {output_file} ذخیره شد')
            )
            
        except Exception as e:
            raise CommandError(f'خطا در تولید خروجی: {str(e)}')

    def build_queryset(self, options):
        """ایجاد کوئری بر اساس فیلترها"""
        queryset = Comment.objects.select_related(
            'user', 'content_type', 'approved_by'
        )
        
        # فیلتر نوع محتوا
        content_type_str = options.get('content_type')
        if content_type_str:
            try:
                app_label, model = content_type_str.split('.')
                content_type = ContentType.objects.get(app_label=app_label, model=model)
                queryset = queryset.filter(content_type=content_type)
            except (ValueError, ContentType.DoesNotExist):
                raise CommandError('نوع محتوای نامعتبر')
        
        # فیلتر آبجکت مشخص
        object_id = options.get('object_id')
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        
        # فیلتر وضعیت
        status = options.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')

    def generate_filename(self, format_type):
        """تولید نام فایل خودکار"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'comments_export_{timestamp}.{format_type}'

    def export_csv(self, queryset, output_file, include_content):
        """خروجی CSV"""
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            # تعریف ستون‌ها
            fieldnames = [
                'id', 'user_name', 'user_username', 'status', 'content_type',
                'object_id', 'likes_count', 'dislikes_count', 'replies_count',
                'approved_by', 'created_at', 'updated_at'
            ]
            
            if include_content:
                fieldnames.insert(4, 'content')
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # نوشتن داده‌ها
            for comment in queryset:
                row = {
                    'id': comment.id,
                    'user_name': getattr(comment.user, 'full_name', ''),
                    'user_username': comment.user.username,
                    'status': comment.get_status_display(),
                    'content_type': f'{comment.content_type.app_label}.{comment.content_type.model}',
                    'object_id': comment.object_id,
                    'likes_count': comment.likes_count,
                    'dislikes_count': comment.dislikes_count,
                    'replies_count': comment.replies_count,
                    'approved_by': getattr(comment.approved_by, 'username', '') if comment.approved_by else '',
                    'created_at': comment.created_at.isoformat(),
                    'updated_at': comment.updated_at.isoformat()
                }
                
                if include_content:
                    row['content'] = comment.content
                
                writer.writerow(row)

    def export_json(self, queryset, output_file, include_content):
        """خروجی JSON"""
        data = []
        
        for comment in queryset:
            item = {
                'id': comment.id,
                'user': {
                    'id': comment.user.id,
                    'username': comment.user.username,
                    'full_name': getattr(comment.user, 'full_name', '')
                },
                'status': comment.status,
                'content_type': f'{comment.content_type.app_label}.{comment.content_type.model}',
                'object_id': comment.object_id,
                'likes_count': comment.likes_count,
                'dislikes_count': comment.dislikes_count,
                'replies_count': comment.replies_count,
                'approved_by': {
                    'id': comment.approved_by.id,
                    'username': comment.approved_by.username
                } if comment.approved_by else None,
                'created_at': comment.created_at.isoformat(),
                'updated_at': comment.updated_at.isoformat()
            }
            
            if include_content:
                item['content'] = comment.content
            
            data.append(item)
        
        with open(output_file, 'w', encoding='utf-8') as jsonfile:
            json.dump({
                'export_info': {
                    'timestamp': datetime.now().isoformat(),
                    'total_count': len(data)
                },
                'comments': data
            }, jsonfile, ensure_ascii=False, indent=2)


# apps/comments/management/__init__.py
"""
Management commands for comments system.
Provides administrative tools for bulk operations and maintenance.
"""

# apps/comments/management/commands/__init__.py
"""
Comments management commands initialization.
"""