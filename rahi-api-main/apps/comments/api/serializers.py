from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

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
    object_id = serializers.IntegerField(write_only=True, required=False)
    parent_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'status', 'user', 'created_at', 'updated_at',
            'likes_count', 'dislikes_count', 'replies_count', 'parent',
            'replies', 'user_reaction', 'is_editable', 'content_type_name',
            # Write-only fields
            'content_type', 'object_id', 'parent_id'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'likes_count', 'dislikes_count', 
            'replies_count', 'created_at', 'updated_at', 'parent'
        ]
    
    def get_replies(self, obj):
        """Get approved replies for this comment"""
        if obj.parent is None:  # Only show replies for top-level comments
            replies = obj.replies.filter(status='APPROVED').order_by('created_at')
            return CommentReplySerializer(replies, many=True, context=self.context).data
        return []
    
    def get_user_reaction(self, obj):
        """Get current user's reaction to this comment"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        try:
            reaction = CommentReaction.objects.get(comment=obj, user=request.user)
            return reaction.reaction_type
        except CommentReaction.DoesNotExist:
            return None
    
    def get_is_editable(self, obj):
        """Check if current user can edit this comment"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        # Owner can edit within 15 minutes, admins can always edit
        if request.user == obj.user:
            time_diff = timezone.now() - obj.created_at
            return time_diff.total_seconds() < 900  # 15 minutes
        
        return hasattr(request.user, 'role') and request.user.role == 0  # Admin
    
    def get_content_type_name(self, obj):
        """Get readable name of the content type"""
        return obj.content_type.model if obj.content_type else None
    
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
    
    def create(self, validated_data):
        """Create new comment"""
        # Remove write-only fields and set proper relations
        content_type_obj = validated_data.pop('content_type_obj')
        target_object = validated_data.pop('target_object')
        parent_obj = validated_data.pop('parent_obj', None)
        
        # Remove the string fields used for validation
        validated_data.pop('content_type', None)
        validated_data.pop('object_id', None) 
        validated_data.pop('parent_id', None)
        
        # Create comment
        comment = Comment.objects.create(
            content_type=content_type_obj,
            object_id=target_object.id,
            parent=parent_obj,
            user=self.context['request'].user,
            **validated_data
        )
        
        return comment
    
    def update(self, instance, validated_data):
        """Update existing comment (only content can be updated)"""
        # Only allow content updates
        if 'content' in validated_data:
            instance.content = validated_data['content']
            instance.save(update_fields=['content', 'updated_at'])
        
        return instance


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