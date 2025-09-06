from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from drf_spectacular.utils import extend_schema_field
from typing import Dict, Any, List

from apps.comments.models import Comment, CommentReaction, CommentModerationLog
from apps.common.serializers import CustomSlugRelatedField

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for comment author display"""
    full_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'full_name']
        read_only_fields = fields


class CommentReactionSerializer(serializers.ModelSerializer):
    """Serializer for comment reactions (likes/dislikes)"""
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = CommentReaction
        fields = ['id', 'user', 'reaction_type', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
    
    def validate_reaction_type(self, value):
        if value not in ['LIKE', 'DISLIKE']:
            raise ValidationError("نوع واکنش باید LIKE یا DISLIKE باشد")
        return value


class CommentSerializer(serializers.ModelSerializer):
    """
    Main comment serializer with support for nested replies,
    user reactions, and content type flexibility.
    """
    user = UserBasicSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()
    is_editable = serializers.SerializerMethodField()
    content_type_name = serializers.SerializerMethodField()
    
    # For creating comments
    content_type = serializers.CharField(write_only=True, required=False)
    # object_id = serializers.IntegerField(write_only=True, required=False)
    object_id = serializers.CharField(write_only=True, required=False)
    # parent_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    parent_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'status', 'user', 'created_at', 'updated_at',
            'likes_count', 'dislikes_count', 'replies_count', 'parent_id',
            'user_reaction', 'is_editable', 'content_type_name', 'replies',
            'object_id', 'content_type'
        ]
    
    @extend_schema_field(serializers.ListSerializer(child=serializers.DictField()))
    def get_replies(self, obj) -> List[Dict[str, Any]]:
        """Get comment replies (returns empty for replies to avoid deep nesting)"""
        if obj.parent is not None:
            return []  # Replies don't show nested replies
        
        try:
            from apps.comments.utils import format_comment_for_display
            replies = obj.replies.filter(status='APPROVED').order_by('created_at')[:5]
            return [
                format_comment_for_display(reply, self.context.get('request', {}).user)
                for reply in replies
            ]
        except Exception:
            return []
    
    @extend_schema_field(serializers.CharField())
    def get_user_reaction(self, obj) -> str:
        """Get current user's reaction to this comment"""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            return 'none'
        
        try:
            from apps.comments.models import CommentReaction
            reaction = CommentReaction.objects.filter(
                comment=obj, 
                user=request.user
            ).first()
            return reaction.reaction_type if reaction else 'none'
        except Exception:
            return 'none'
    
    @extend_schema_field(serializers.CharField())
    def get_content_type_name(self, obj) -> str:
        """Get content type name for the commented object"""
        return obj.content_type.model if obj.content_type else ''
    
    def validate_content(self, value):
        """Validate comment content"""
        if len(value.strip()) < 5:
            raise ValidationError("نظر باید حداقل 5 کاراکتر داشته باشد")
        
        if len(value) > 2000:
            raise ValidationError("نظر نمی‌تواند بیشتر از 2000 کاراکتر باشد")
        
        return value.strip()
    
    def validate(self, attrs):
        """Validate comment creation data"""
        request = self.context.get('request')
        
        # For creating new comment, we need content_type and object_id
        if not self.instance:
            content_type_str = attrs.get('content_type')
            object_id = attrs.get('object_id')
            parent_id = attrs.get('parent_id')
            
            if not content_type_str or not object_id:
                raise ValidationError("content_type و object_id الزامی است")
            
            # Validate content type
            try:
                app_label, model = content_type_str.split('.')
                content_type = ContentType.objects.get(app_label=app_label, model=model)
                attrs['content_type_obj'] = content_type
            except (ValueError, ContentType.DoesNotExist):
                raise ValidationError("نوع محتوای نامعتبر")
            
            # Validate object exists
            try:
                target_object = content_type.get_object_for_this_type(id=object_id)
                attrs['target_object'] = target_object
            except:
                raise ValidationError("آبجکت مورد نظر یافت نشد")
            
            # Validate parent comment if provided
            if parent_id:
                try:
                    parent_comment = Comment.objects.get(
                        id=parent_id,
                        content_type=content_type,
                        object_id=object_id,
                        status='APPROVED'
                    )
                    attrs['parent_obj'] = parent_comment
                    
                    # Prevent deep nesting (max 1 level of replies)
                    if parent_comment.parent is not None:
                        raise ValidationError("نمی‌توان به پاسخ‌ها پاسخ داد")
                        
                except Comment.DoesNotExist:
                    raise ValidationError("نظر والد یافت نشد")
        
        return attrs
    
    def get_is_editable(self, obj) -> bool:
        """Check if comment is editable by current user."""
        from apps.comments.utils import is_comment_editable  # local import to avoid cycles
        request = self.context.get('request')
        return bool(request and hasattr(request, 'user') and is_comment_editable(request.user, obj))  # <— fix

    def validate(self, attrs):
        """
        When creating a comment we must validate the content type and target object.
        object_id is a string (UUID or int-string) and passed verbatim to the GFK lookup.
        """
        if self.instance:
            return attrs

        content_type_str = attrs.get('content_type')
        object_id = attrs.get('object_id')
        parent_id = attrs.get('parent_id')

        if not content_type_str or not object_id:
            raise ValidationError("content_type و object_id الزامی است")

        try:
            app_label, model = content_type_str.split('.')
            content_type = ContentType.objects.get(app_label=app_label, model=model)
            attrs['content_type_obj'] = content_type
        except (ValueError, ContentType.DoesNotExist):
            raise ValidationError("نوع محتوای نامعتبر")

        # Let ContentType handle UUIDs transparently
        try:
            target_object = content_type.get_object_for_this_type(id=object_id)
            attrs['target_object'] = target_object
        except Exception:
            raise ValidationError("آبجکت مورد نظر یافت نشد")

        if parent_id:
            try:
                parent_comment = Comment.objects.get(
                    id=parent_id,
                    content_type=content_type,
                    object_id=str(object_id),  # <— ensure string compare
                    status='APPROVED',
                )
                if parent_comment.parent is not None:
                    raise ValidationError("نمی‌توان به پاسخ‌ها پاسخ داد")
                attrs['parent_obj'] = parent_comment
            except Comment.DoesNotExist:
                raise ValidationError("نظر والد یافت نشد")

        return attrs

    def create(self, validated_data):
        # Strip helper fields and create the comment
        content_type_obj = validated_data.pop('content_type_obj')
        target_object    = validated_data.pop('target_object')
        parent_obj       = validated_data.pop('parent_obj', None)
        validated_data.pop('content_type', None)
        validated_data.pop('object_id', None)
        validated_data.pop('parent_id', None)

        return Comment.objects.create(
            content_type=content_type_obj,
            object_id=str(target_object.id),  # <— always store as string
            parent=parent_obj,
            user=self.context['request'].user,
            **validated_data,
        )

class CommentReplySerializer(CommentSerializer):
    """Simplified serializer for comment replies (no nested replies)"""
    
    class Meta(CommentSerializer.Meta):
        fields = [
            'id', 'content', 'status', 'user', 'created_at', 'updated_at',
            'likes_count', 'dislikes_count', 'user_reaction', 'is_editable'
        ]
    
    def get_replies(self, obj):
        """Replies don't show nested replies"""
        return []


class CommentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for comment lists"""
    user = UserBasicSerializer(read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)
    
    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'status', 'user', 'created_at',
            'likes_count', 'dislikes_count', 'replies_count',
            'content_type_name'
        ]
        read_only_fields = fields


class CommentModerationSerializer(serializers.ModelSerializer):
    """Serializer for admin comment moderation"""
    comment = CommentListSerializer(read_only=True)
    moderator = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = CommentModerationLog
        fields = ['id', 'comment', 'moderator', 'action', 'reason', 'created_at']
        read_only_fields = ['id', 'comment', 'moderator', 'created_at']


class BulkCommentActionSerializer(serializers.Serializer):
    """Serializer for bulk comment actions"""
    comment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100
    )
    action = serializers.ChoiceField(choices=['approve', 'reject', 'delete'])
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_comment_ids(self, value):
        """Validate that all comment IDs exist"""
        existing_ids = Comment.objects.filter(id__in=value).values_list('id', flat=True)
        missing_ids = set(value) - set(existing_ids)
        
        if missing_ids:
            raise ValidationError(f"نظرات با شناسه‌های {list(missing_ids)} یافت نشدند")
        
        return value


class CommentExportSerializer(serializers.ModelSerializer):
    """Serializer for exporting comments data"""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)
    parent_content = serializers.CharField(source='parent.content', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    
    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'status', 'user_name', 'user_username',
            'content_type_name', 'object_id', 'parent_content',
            'likes_count', 'dislikes_count', 'replies_count',
            'approved_by_name', 'approved_at', 'created_at', 'updated_at'
        ]