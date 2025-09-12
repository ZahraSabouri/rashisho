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