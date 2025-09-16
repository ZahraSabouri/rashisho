from rest_framework import serializers
from apps.project.models import Team, TeamChatMessage, TeamOnlineMeeting, TeamUnstableTask
from django.contrib.auth import get_user_model

User = get_user_model()


class TeamChatMessageSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = TeamChatMessage
        fields = [
            'id', 'message', 'user_name', 'user_avatar', 'user_role',
            'created_at', 'time_ago', 'is_edited', 'edited_at'
        ]
        read_only_fields = ['id', 'created_at', 'is_edited', 'edited_at']
    
    def get_user_avatar(self, obj):
        if obj.user.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.user.avatar.url)
        return None
    
    def get_user_role(self, obj):
        # Get user role in this team
        membership = obj.team.requests.filter(
            user=obj.user, status='A', request_type='JOIN'
        ).first()
        return membership.get_user_role_display() if membership else 'عضو'
    
    def get_time_ago(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} ساعت پیش"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} دقیقه پیش"
        else:
            return "همین الان"


class TeamOnlineMeetingSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = TeamOnlineMeeting
        fields = [
            'id', 'title', 'meeting_url', 'description', 'scheduled_for',
            'is_active', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'created_by_name']


class TeamUnstableTaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = TeamUnstableTask
        fields = [
            'id', 'title', 'description', 'file_url', 'assigned_to_name',
            'due_date', 'is_completed', 'completed_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'completed_at']
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class TeamMemberDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    avatar = serializers.URLField(allow_null=True)
    role = serializers.CharField()
    role_code = serializers.CharField()
    is_leader = serializers.BooleanField()
    is_deputy = serializers.BooleanField()
    latest_education = serializers.DictField(allow_null=True)
    joined_at = serializers.DateTimeField()


class TeamPageSerializer(serializers.ModelSerializer):
    team_members = serializers.SerializerMethodField()
    recent_messages = serializers.SerializerMethodField()
    meeting_links = serializers.SerializerMethodField()
    pending_tasks = serializers.SerializerMethodField()
    team_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Team
        fields = [
            'id', 'title', 'description', 'team_code', 'team_building_stage',
            'team_building_stage_display', 'member_count', 'count',
            'team_members', 'recent_messages', 'meeting_links', 
            'pending_tasks', 'team_stats', 'created_at'
        ]
        read_only_fields = ['team_code', 'member_count']
    
    def get_team_members(self, obj):
        member_details = obj.get_team_member_details()
        return TeamMemberDetailSerializer(member_details, many=True).data
    
    def get_recent_messages(self, obj):
        recent_messages = obj.get_latest_chat_messages(limit=10)
        return TeamChatMessageSerializer(
            recent_messages, many=True, context=self.context
        ).data
    
    def get_meeting_links(self, obj):
        active_meetings = obj.get_active_meeting_links()
        return TeamOnlineMeetingSerializer(
            active_meetings, many=True, context=self.context
        ).data
    
    def get_pending_tasks(self, obj):
        pending_tasks = obj.get_pending_unstable_tasks()
        return TeamUnstableTaskSerializer(
            pending_tasks, many=True, context=self.context
        ).data
    
    def get_team_stats(self, obj):
        return {
            'total_messages': obj.chat_messages.count(),
            'total_meetings': obj.online_meetings.filter(is_active=True).count(),
            'completed_tasks': obj.unstable_tasks.filter(is_completed=True).count(),
            'pending_tasks': obj.unstable_tasks.filter(is_completed=False).count(),
        }


class CreateChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamChatMessage
        fields = ['message']
    
    def create(self, validated_data):
        team = self.context['team']
        user = self.context['request'].user
        
        # Verify user is team member
        membership = team.requests.filter(
            user=user, status='A', request_type='JOIN'
        ).first()
        
        if not membership:
            raise serializers.ValidationError("شما عضو این تیم نیستید!")
        
        return TeamChatMessage.objects.create(
            team=team,
            user=user,
            **validated_data
        )
