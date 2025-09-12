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