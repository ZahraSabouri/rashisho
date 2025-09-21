from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers
from apps.project import models


class TeamDiscoverySerializer(serializers.ModelSerializer):
    leader_info = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True)
    formation_status = serializers.SerializerMethodField()
    province_name = serializers.SerializerMethodField()
    project_info = serializers.SerializerMethodField()
    is_accepting_members = serializers.SerializerMethodField()
    team_stage_display = serializers.CharField(
        source='get_team_building_stage_display', 
        read_only=True
    )
    
    class Meta:
        model = models.Team
        fields = [
            'id', 'title', 'description', 'team_code', 'count',
            'team_building_stage', 'team_stage_display',
            'leader_info', 'member_count', 'formation_status',
            'province_name', 'project_info', 'is_accepting_members',
            'created_at'
        ]
    
    def get_leader_info(self, obj):
        """Get team leader information"""
        leader_request = obj.requests.filter(
            user_role='C', status='A', request_type='JOIN'
        ).select_related('user').first()
        
        if leader_request:
            leader = leader_request.user
            return {
                'id': leader.id,
                'name': leader.full_name,
                'avatar_url': (
                    self.context['request'].build_absolute_uri(leader.avatar.url)
                    if leader.avatar and self.context.get('request') else None
                )
            }
        return None
    
    def get_formation_status(self, obj):
        """Get formation status of the team"""
        member_count = getattr(obj, 'member_count', obj.get_member_count())
        
        if member_count >= 2:
            status = 'formed'
            status_label = 'تشکیل شده'
        elif member_count >= 1:
            status = 'forming'
            status_label = 'در حال تشکیل'
        else:
            status = 'empty'
            status_label = 'خالی'
        
        return {
            'status': status,
            'label': status_label,
            'is_complete': member_count >= obj.count,
            'completion_percentage': int((member_count / obj.count) * 100) if obj.count > 0 else 0
        }
    
    def get_province_name(self, obj):
        """Get province name based on team leader's location"""
        leader_request = obj.requests.filter(
            user_role='C', status='A', request_type='JOIN'
        ).select_related('user', 'user__resume').first()
        
        if leader_request:
            user = leader_request.user
            resume = getattr(user, 'resume', None)
            
            # Try team formation province first
            if resume and hasattr(resume, 'team_formation_province'):
                return resume.team_formation_province.title
            # Fallback to user's city province
            elif user.city and hasattr(user.city, 'province'):
                return user.city.province.title
        
        return None
    
    def get_project_info(self, obj):
        """Get basic project information"""
        if obj.project:
            return {
                'id': obj.project.id,
                'title': obj.project.title,
                'short_description': (
                    obj.project.description[:100] + '...' 
                    if len(obj.project.description) > 100 
                    else obj.project.description
                )
            }
        return None
    
    def get_is_accepting_members(self, obj):
        """Check if team is currently accepting new members"""
        member_count = getattr(obj, 'member_count', obj.get_member_count())
        
        # Check capacity
        if member_count >= obj.count:
            return False
        
        # Check if formation is enabled for this stage
        if not obj.is_formation_allowed():
            return False
        
        # Check if team is in dissolution
        if obj.is_dissolution_in_progress:
            return False
        
        return True


class TeamJoinOptionsSerializer(serializers.Serializer):
    """Serializer for team join options"""
    
    team = TeamDiscoverySerializer(read_only=True)
    can_join = serializers.BooleanField()
    current_members = serializers.IntegerField()
    max_members = serializers.IntegerField()
    available_spots = serializers.IntegerField()
    available_actions = serializers.SerializerMethodField()
    
    def get_available_actions(self, obj):
        """Get available actions for joining this team"""
        if obj.get('can_join', False):
            return [
                {
                    'action': 'request_join',
                    'label': 'درخواست عضویت',
                    'description': 'ارسال درخواست عضویت در این تیم',
                    'requires_approval': True
                }
            ]
        return []


class TeamMemberInfoSerializer(serializers.Serializer):
    """Serializer for team member information in discovery"""
    
    id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField()
    role_display = serializers.CharField()
    avatar_url = serializers.URLField(allow_null=True)
    is_leader = serializers.BooleanField()
    is_deputy = serializers.BooleanField()
    joined_at = serializers.DateTimeField()


class DetailedTeamDiscoverySerializer(TeamDiscoverySerializer):
    """Extended serializer with complete team information"""
    
    all_members = serializers.SerializerMethodField()
    recent_activity = serializers.SerializerMethodField()
    team_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = models.Team
        fields = TeamDiscoverySerializer.Meta.fields + [
            'all_members', 'recent_activity', 'team_stats'
        ]
    
    def get_all_members(self, obj):
        """Get all team members information"""
        members = obj.requests.filter(
            status='A', request_type='JOIN'
        ).select_related('user').order_by(
            'user_role', 'created_at'
        )
        
        member_data = []
        for member in members:
            user = member.user
            member_data.append({
                'id': user.id,
                'name': user.full_name,
                'role': member.user_role,
                'role_display': member.get_user_role_display(),
                'avatar_url': (
                    self.context['request'].build_absolute_uri(user.avatar.url)
                    if user.avatar and self.context.get('request') else None
                ),
                'is_leader': member.user_role == 'C',
                'is_deputy': member.user_role == 'D',
                'joined_at': member.created_at
            })
        
        return member_data
    
    def get_recent_activity(self, obj):
        """Get recent team activity"""
        # Get recent chat messages count
        recent_messages = obj.chat_messages.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # Get recent task activities
        recent_tasks = obj.unstable_tasks.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        return {
            'recent_messages': recent_messages,
            'recent_tasks': recent_tasks,
            'last_activity': obj.chat_messages.order_by('-created_at').first().created_at if obj.chat_messages.exists() else obj.created_at
        }
    
    def get_team_stats(self, obj):
        """Get team statistics"""
        return {
            'total_messages': obj.chat_messages.count(),
            'active_meetings': obj.online_meetings.filter(is_active=True).count(),
            'completed_tasks': obj.unstable_tasks.filter(is_completed=True).count(),
            'pending_tasks': obj.unstable_tasks.filter(is_completed=False).count()
        }