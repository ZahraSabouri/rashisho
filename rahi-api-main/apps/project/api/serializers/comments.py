from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType

from apps.comments.api.serializers import CommentSerializer, CommentListSerializer
from apps.comments.models import Comment
from apps.project.models import Project


class ProjectCommentSerializer(CommentSerializer):
    """
    Serializer for project comments with automatic content_type handling.
    Simplifies API by auto-setting content_type to 'project.project'.
    """
    # project_id = serializers.IntegerField(write_only=True, source='object_id')
    # project_title = serializers.CharField(source='content_object.title', read_only=True)
    project_id = serializers.UUIDField(write_only=True, source='object_id')
    project_title = serializers.CharField(source='content_object.title', read_only=True)

    class Meta(CommentSerializer.Meta):
        fields = CommentSerializer.Meta.fields + ['project_id', 'project_title']
        # Remove content_type from required fields since we auto-set it
        extra_kwargs = {
            **CommentSerializer.Meta.extra_kwargs,
            'content_type': {'required': False, 'write_only': True},
            'object_id': {'write_only': True},
        }

    def validate_project_id(self, value):
        """Validate that the project exists and is accessible"""
        try:
            project = Project.objects.get(id=value)
            if not project.can_be_selected:
                raise serializers.ValidationError("این پروژه قابل انتخاب نیست")
            return value
        except Project.DoesNotExist:
            raise serializers.ValidationError("پروژه مورد نظر یافت نشد")
        
    def validate_parent_id(self, value):
        """Ensure parent comment belongs to the same project and is a project comment."""
        if value is None:
            return value
        try:
            parent = Comment.objects.get(id=value)
            if parent.content_type.model != 'project':
                raise serializers.ValidationError("کامنت والد باید مربوط به پروژه باشد")
            # Compare as strings because Comment.object_id is CharField
            requested_pid = str(self.initial_data.get('project_id'))
            if str(parent.object_id) != requested_pid:
                raise serializers.ValidationError("کامنت والد باید مربوط به همین پروژه باشد")
            if parent.parent is not None:
                raise serializers.ValidationError("فقط یک سطح پاسخ مجاز است")
            return value
        except Comment.DoesNotExist:
            raise serializers.ValidationError("کامنت والد یافت نشد")

    def validate(self, attrs):
        """Auto-set content_type to project model"""
        # Auto-set content type for projects
        project_content_type = ContentType.objects.get_for_model(Project)
        attrs['content_type'] = project_content_type
        
        # Call parent validation
        return super().validate(attrs)

    def to_representation(self, instance):
        """Add project-specific information to response"""
        data = super().to_representation(instance)
        
        # Add project-specific context
        if hasattr(instance, 'content_object') and instance.content_object:
            project = instance.content_object
            data['project'] = {
                'id': project.id,
                'title': project.title,
                'code': project.code,
                'status': project.status_display
            }
        
        # Add user's reaction to this comment (if authenticated)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user_reaction = instance.reactions.filter(user=request.user).first()
            data['user_reaction'] = user_reaction.reaction_type if user_reaction else None
        
        return data


class ProjectCommentListSerializer(CommentListSerializer):
    """
    List serializer for project comments with minimal project info.
    Optimized for list views with reduced data.
    """
    project_title = serializers.CharField(source='content_object.title', read_only=True)
    project_code = serializers.CharField(source='content_object.code', read_only=True)
    
    class Meta(CommentListSerializer.Meta):
        fields = CommentListSerializer.Meta.fields + ['project_title', 'project_code']

    def to_representation(self, instance):
        """Add minimal project info for list view"""
        data = super().to_representation(instance)
        
        # Add user's reaction status
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user_reaction = instance.reactions.filter(user=request.user).first()
            data['user_reaction'] = user_reaction.reaction_type if user_reaction else None
        
        return data


class ProjectCommentCreateSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for creating project comments.
    Only requires content and project_id.
    """
    # project_id = serializers.IntegerField()
    project_id = serializers.CharField()
    # parent_id = serializers.IntegerField(required=False, allow_null=True)
    parent_id = serializers.CharField(required=False, allow_null=True)
    
    class Meta:
        model = Comment
        fields = ['content', 'project_id', 'parent_id']
        extra_kwargs = {
            'content': {
                'min_length': 5,
                'max_length': 2000,
                'error_messages': {
                    'min_length': 'نظر باید حداقل ۵ کاراکتر باشد',
                    'max_length': 'نظر نمی‌تواند بیش از ۲۰۰۰ کاراکتر باشد'
                }
            }
        }

    def validate_project_id(self, value):
        """Validate project exists and is accessible"""
        try:
            project = Project.objects.get(id=value)
            if not project.visible or not project.is_active:
                raise serializers.ValidationError("این پروژه در دسترس نیست")
            return value
        except Project.DoesNotExist:
            raise serializers.ValidationError("پروژه مورد نظر یافت نشد")

    def validate_parent_id(self, value):
        """Validate parent comment exists and belongs to same project"""
        if value is not None:
            try:
                parent = Comment.objects.get(id=value)
                
                # Check if parent belongs to a project
                if parent.content_type.model != 'project':
                    raise serializers.ValidationError("کامنت والد باید مربوط به پروژه باشد")
                
                # Check if parent belongs to same project
                requested_pid = str(self.initial_data.get('project_id'))
                if str(parent.object_id) != requested_pid:
                    raise serializers.ValidationError("کامنت والد باید مربوط به همین پروژه باشد")
                
                # Check reply depth (only 1 level allowed)
                if parent.parent is not None:
                    raise serializers.ValidationError("فقط یک سطح پاسخ مجاز است")
                
                return value
            except Comment.DoesNotExist:
                raise serializers.ValidationError("کامنت والد یافت نشد")
        return value


class ProjectCommentStatsSerializer(serializers.Serializer):
    """Serializer for project comment statistics"""
    total_comments = serializers.IntegerField()
    approved_comments = serializers.IntegerField()
    pending_comments = serializers.IntegerField()
    rejected_comments = serializers.IntegerField()
    total_likes = serializers.IntegerField()
    total_dislikes = serializers.IntegerField()
    engagement_rate = serializers.FloatField()
    top_contributors = serializers.ListField(child=serializers.DictField())
    recent_activity = serializers.ListField(child=serializers.DictField())


class ProjectCommentModerationSerializer(serializers.Serializer):
    """Serializer for comment moderation actions"""
    action = serializers.ChoiceField(choices=['approve', 'reject', 'delete'])
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    comment_ids = serializers.ListField(
        # child=serializers.IntegerField(),
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100
    )

    def validate_comment_ids(self, value):
        """Validate all comment IDs exist and are project comments"""
        project_content_type = ContentType.objects.get_for_model(Project)
        existing_comments = Comment.objects.filter(
            id__in=value,
            content_type=project_content_type
        ).values_list('id', flat=True)
        
        missing_ids = set(value) - set(existing_comments)
        if missing_ids:
            raise serializers.ValidationError(
                f"کامنت‌های با شناسه‌های {list(missing_ids)} یافت نشدند یا مربوط به پروژه نیستند"
            )
        
        return value