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