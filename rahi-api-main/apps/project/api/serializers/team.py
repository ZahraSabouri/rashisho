import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.account.models import User
from apps.common.serializers import CustomSlugRelatedField
from apps.project import models
from apps.resume.api.serializers import education, skill
from apps.resume.models import Resume

import datetime
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils import timezone

from apps.account.models import User
from apps.common.serializers import CustomSlugRelatedField
from apps.project import models
from apps.resume.api.serializers import education, skill
from apps.resume.models import Resume

from django.contrib.auth import get_user_model

User = get_user_model()


class TeamRequestSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(queryset=models.Team.objects.all())
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    
    class Meta:
        model = models.TeamRequest
        fields = [
            'id', 'team', 'user', 'status', 'user_role', 'request_type',
            'requested_by', 'description'
        ]

    def validate(self, attrs) -> Dict[str, Any]:
        team = attrs.get('team')
        user = attrs.get('user')
        request_type = attrs.get('request_type', 'JOIN')
        
        if request_type == 'JOIN':
            # Check if user already in a team
            existing_membership = models.TeamRequest.objects.filter(
                user=user, status='A', request_type='JOIN'
            ).first()
            if existing_membership:
                raise serializers.ValidationError("کاربر قبلاً عضو تیمی است!")
            
            # Check team capacity
            current_members = team.get_member_count()
            if current_members >= team.count:
                raise serializers.ValidationError("ظرفیت تیم تکمیل است!")
        
        elif request_type == 'LEAVE':
            # Check if user is actually a member
            membership = models.TeamRequest.objects.filter(
                user=user, team=team, status='A', request_type='JOIN'
            ).first()
            if not membership:
                raise serializers.ValidationError("شما عضو این تیم نیستید!")
            
            # Leaders cannot leave directly (must dissolve team)
            if membership.user_role == 'C':
                raise serializers.ValidationError("سرگروه باید تیم را منحل کند!")
        
        elif request_type == 'INVITE':
            # Check if inviter is team leader or deputy
            inviter = self.context['request'].user
            leader_membership = models.TeamRequest.objects.filter(
                user=inviter, team=team, status='A', user_role__in=['C', 'D']
            ).first()
            if not leader_membership:
                raise serializers.ValidationError("فقط سرگروه یا قائم مقام می‌تواند دعوت کند!")
        
        return super().validate(attrs)


class TeamSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    leader = serializers.SerializerMethodField()
    deputy = serializers.SerializerMethodField()
    leadership = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    is_user_member = serializers.SerializerMethodField()
    user_role_in_team = serializers.SerializerMethodField()
    user_leadership_role = serializers.SerializerMethodField()
    can_user_leave = serializers.SerializerMethodField()
    can_user_dissolve = serializers.SerializerMethodField()
    can_user_manage_team = serializers.SerializerMethodField()
    dissolution_status = serializers.SerializerMethodField()
    
    # Include team_code and stage info
    team_code = serializers.CharField(read_only=True)
    team_building_stage = serializers.IntegerField()
    team_building_stage_display = serializers.CharField(
        source='get_team_building_stage_display', 
        read_only=True
    )
    
    # For team creation - backwards compatibility
    teammate = serializers.SlugRelatedField(
        slug_field="user_info__id", 
        queryset=User.objects.all(), 
        many=True, 
        write_only=True, 
        required=False
    )

    class Meta:
        model = models.Team
        fields = [
            'id', 'title', 'description', 'count', 'project', 'create_date',
            'team_code', 'team_building_stage', 'team_building_stage_display',
            'member_count', 'leader', 'deputy', 'leadership', 'members',
            'is_user_member', 'user_role_in_team', 'user_leadership_role',
            'can_user_leave', 'can_user_dissolve', 'can_user_manage_team',
            'dissolution_status', 'teammate'
        ]
        read_only_fields = [
            'project', 'member_count', 'leader', 'deputy', 'leadership', 
            'members', 'team_code'
        ]

    def get_member_count(self, obj) -> int:
        return obj.get_member_count()
    
    def get_leader(self, obj) -> Optional[Dict[str, Any]]:
        leader_request = obj.requests.filter(user_role="C", status="A", request_type="JOIN").first()
        if leader_request:
            return {
                'id': leader_request.user.id,
                'full_name': leader_request.user.full_name,
                'avatar': leader_request.user.avatar.url if leader_request.user.avatar else None,
                'role': 'leader',
                'role_display': 'سرگروه',
                'joined_at': leader_request.created_at
            }
        return None
    
    def get_deputy(self, obj) -> Optional[Dict[str, Any]]:
        deputy_request = obj.requests.filter(user_role="D", status="A", request_type="JOIN").first()
        if deputy_request:
            return {
                'id': deputy_request.user.id,
                'full_name': deputy_request.user.full_name,
                'avatar': deputy_request.user.avatar.url if deputy_request.user.avatar else None,
                'role': 'deputy',
                'role_display': 'قائم مقام',
                'joined_at': deputy_request.created_at
            }
        return None
    
    def get_leadership(self, obj) -> List[Dict[str, Any]]:
        """Get both leader and deputy as leadership team"""
        leadership_requests = obj.requests.filter(
            user_role__in=["C", "D"], 
            status="A", 
            request_type="JOIN"
        ).order_by('-user_role')  # Leader first, then deputy
        
        leadership_data = []
        for leader in leadership_requests:
            leadership_data.append({
                'id': leader.user.id,
                'full_name': leader.user.full_name,
                'avatar': leader.user.avatar.url if leader.user.avatar else None,
                'role': leader.user_role,
                'role_display': leader.get_user_role_display(),
                'is_leader': leader.user_role == 'C',
                'is_deputy': leader.user_role == 'D',
                'joined_at': leader.created_at
            })
        
        return leadership_data
    
    def get_members(self, obj) -> List[Dict[str, Any]]:
        members = obj.requests.filter(
            status='A', 
            request_type='JOIN'
        ).select_related('user')
        
        member_data = []
        for member in members:
            member_data.append({
                'id': member.user.id,
                'full_name': member.user.full_name,
                'avatar': member.user.avatar.url if member.user.avatar else None,
                'user_role': member.get_user_role_display(),
                'is_leader': member.user_role == 'C',
                'is_deputy': member.user_role == 'D',
                'joined_at': member.created_at
            })
        
        return member_data
    
    def get_is_user_member(self, obj) -> bool:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.requests.filter(
                user=request.user, 
                status='A', 
                request_type='JOIN'
            ).exists()
        return False
    
    def get_user_role_in_team(self, obj) -> Optional[Dict[str, Any]]:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            member = obj.requests.filter(
                user=request.user, 
                status='A', 
                request_type='JOIN'
            ).first()
            if member:
                return {
                    'role': member.user_role,
                    'role_display': member.get_user_role_display(),
                    'is_leader': member.user_role == 'C',
                    'is_deputy': member.user_role == 'D'
                }
        return None
    
    def get_user_leadership_role(self, obj) -> Optional[Dict[str, Any]]:
        """Get user's leadership role if any"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            leadership = obj.requests.filter(
                user=request.user,
                user_role__in=['C', 'D'],
                status='A',
                request_type='JOIN'
            ).first()
            
            if leadership:
                return {
                    'role': leadership.user_role,
                    'role_display': leadership.get_user_role_display(),
                    'is_leader': leadership.user_role == 'C',
                    'is_deputy': leadership.user_role == 'D',
                    'can_promote_deputy': leadership.user_role == 'C',
                    'can_demote_deputy': leadership.user_role == 'C'
                }
        return None
    
    def get_can_user_leave(self, obj) -> bool:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            member = obj.requests.filter(
                user=request.user, 
                status='A', 
                request_type='JOIN'
            ).first()
            # Members can leave, but leaders must dissolve
            return member and member.user_role not in ['C']
        return False
    
    def get_can_user_dissolve(self, obj) -> bool:
        """Only leaders can dissolve teams (not deputies)"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            leader = obj.requests.filter(
                user=request.user, 
                status='A', 
                user_role='C',  # Only leaders, not deputies
                request_type='JOIN'
            ).first()
            return bool(leader)
        return False
    
    def get_can_user_manage_team(self, obj) -> bool:
        """Check if current user can manage team (leader or deputy)"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.requests.filter(
                user=request.user,
                user_role__in=['C', 'D'],
                status='A',
                request_type='JOIN'
            ).exists()
        return False
    
    def get_dissolution_status(self, obj) -> Dict[str, Any]:
        if obj.is_dissolution_in_progress:
            return {
                'in_progress': True,
                'requested_by': obj.dissolution_requested_by.full_name if obj.dissolution_requested_by else None,
                'requested_at': obj.dissolution_requested_at,
                'can_cancel': self.get_can_user_dissolve(obj)
            }
        return {'in_progress': False}

    def validate(self, attrs) -> Dict[str, Any]:
        # Ensure team_building_stage is valid
        stage = attrs.get('team_building_stage', 4)
        if stage not in [1, 2, 3, 4]:
            raise serializers.ValidationError(
                "مرحله تیم‌سازی باید بین 1 تا 4 باشد"
            )
        return super().validate(attrs)

    def create(self, validated_data) -> models.Team:
        teammates = validated_data.pop("teammate", [])
        
        # Set default stage if not provided
        if 'team_building_stage' not in validated_data:
            validated_data['team_building_stage'] = 4
            
        team = models.Team.objects.create(**validated_data)
        
        # Backwards compatibility for teammate field
        if teammates:
            for teammate in teammates:
                models.TeamRequest.objects.create(
                    team=team, 
                    user=teammate, 
                    user_role="M", 
                    status="A", 
                    request_type="JOIN"
                )
        return team


class TeamListSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    leader_name = serializers.SerializerMethodField()
    is_forming = serializers.SerializerMethodField()
    
    class Meta:
        model = models.Team
        fields = [
            'id', 'title', 'team_code', 'team_building_stage_display',
            'member_count', 'count', 'leader_name', 'is_forming'
        ]
    
    def get_member_count(self, obj) -> int:
        return obj.get_member_count()
    
    def get_leader_name(self, obj) -> Optional[str]:
        leader = obj.get_leader_user()
        return leader.full_name if leader else None
    
    def get_is_forming(self, obj) -> bool:
        return obj.get_member_count() < obj.count


class TeammateInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["user_id", "full_name", "user_info", "avatar"]
        read_only_fields = ["user_id", "full_name"]

    def to_representation(self, instance) -> Dict[str, Any]:  # Fixed: removed type annotation on instance
        rep = super().to_representation(instance)
        user_resume = Resume.objects.filter(user=instance).first()
        rep["user_info"] = {
            "email": instance.user_info["email"] if instance.user_info.get("email", None) else None,
            "mobile_number": instance.user_info["mobile_number"],
        }
        if user_resume:
            rep["educations"] = []
            user_educations = user_resume.educations.all()
            for user_education in user_educations:
                from apps.account.api.serializers import education
                rep["educations"].append(education.EducationSerializer(user_education).data)

            rep["skills"] = []
            user_skills = user_resume.skills.all()
            for user_skill in user_skills:
                from apps.account.api.serializers import skill
                rep["skills"].append(skill.SkillSerializer(user_skill).data)

        return rep


class UserTeamInfoSerializer(serializers.ModelSerializer):
    has_team = serializers.SerializerMethodField()
    team_role = serializers.SerializerMethodField()
    pending_requests = serializers.SerializerMethodField()
    attractive_projects = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'avatar', 'has_team', 'team_role', 
            'pending_requests', 'attractive_projects'
        ]
    
    def get_has_team(self, obj) -> Optional[Dict[str, Any]]:
        team_request = models.TeamRequest.objects.filter(
            user=obj, status='A', request_type='JOIN'
        ).first()
        if team_request:
            return {
                'id': team_request.team.id,
                'title': team_request.team.title
            }
        return None
    
    def get_team_role(self, obj) -> Optional[str]:
        team_request = models.TeamRequest.objects.filter(
            user=obj, status='A', request_type='JOIN'
        ).first()
        return team_request.get_user_role_display() if team_request else None
    
    def get_pending_requests(self, obj) -> List[Dict[str, Any]]:
        pending = models.TeamRequest.objects.filter(
            user=obj, status='W'
        ).select_related('team')
        
        return [{
            'id': req.id,
            'team_title': req.team.title,
            'request_type': req.get_request_type_display(),
            'created_at': req.created_at
        } for req in pending]
    
    def get_attractive_projects(self, obj) -> List[Dict[str, Any]]:
        # Get user's attractive projects
        try:
            from apps.project.models import ProjectAttraction
            attractions = ProjectAttraction.objects.filter(
                user=obj
            ).select_related('project').order_by('priority')
            
            return [{
                'id': attr.project.id,
                'title': attr.project.title,
                'priority': attr.priority
            } for attr in attractions]
        except:
            return []


class UsersTeamRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["user_id", "full_name", "avatar"]
        read_only_fields = ["user_id", "full_name"]

    def to_representation(self, instance) -> Dict[str, Any]:
        rep = super().to_representation(instance)
        user_resume = Resume.objects.filter(user=instance).first()
        rep["user_info"] = {
            "email": instance.user_info["email"] if instance.user_info.get("email", None) else None,
            "mobile_number": instance.user_info["mobile_number"],
        }
        if user_resume:
            rep["educations"] = []
            user_educations = user_resume.educations.all()
            for user_education in user_educations:
                from apps.account.api.serializers import education
                rep["educations"].append(education.EducationSerializer(user_education).data)

            rep["skills"] = []
            user_skills = user_resume.skills.all()
            for user_skill in user_skills:
                from apps.account.api.serializers import skill
                rep["skills"].append(skill.SkillSerializer(user_skill).data)

        return rep


class AdminTeamRequestSerializer(serializers.ModelSerializer):
    user = CustomSlugRelatedField(slug_field="full_name", queryset=User.objects.all())

    class Meta:
        model = models.TeamRequest
        fields = ["user", "user_role"]


class AdminTeamCreateSerializer(serializers.ModelSerializer):
    teammates = AdminTeamRequestSerializer(write_only=True, many=True)
    requests = AdminTeamRequestSerializer(read_only=True, many=True)

    class Meta:
        model = models.Team
        fields = ["id", "description", "title", "count", "project", "teammates", "requests"]

    def validate(self, attrs):
        if len(attrs.get("teammates", None)) > attrs.get("count", None):
            raise ValidationError("تعداد اعضا مطابقت ندارد!")

        user_role_list = []
        teammates = attrs.get("teammates", None)
        for teammate in teammates:
            team_request = models.TeamRequest.objects.filter(user_id=teammate.get("user"), status="A").first()
            if teammate.get("user_role") == "C":
                user_role_list.append(teammate.get("user_role"))

            if team_request:
                if (
                    self.context.get("request").method == "PATCH"
                    and team_request.user_role == "C"
                    and not str(team_request.team.id) == self.context.get("kwargs").get("pk")
                ):
                    raise ValidationError(
                        f" {team_request.user.full_name} در تیم قبلی خود مسئول تیم است و نمیتواند از آن تیم حذف شده و به تیم جدید اضافه شود."
                    )

                if self.context.get("request").method == "POST" and team_request.user_role == "C":
                    raise ValidationError(
                        f" {team_request.user.full_name} در تیم قبلی خود مسئول تیم است و نمیتواند از آن تیم حذف شده و به تیم جدید اضافه شود."
                    )

                team_request.delete()

        if len(user_role_list) != 1:
            raise ValidationError("مسئول تیم فقط یک نفر می تواند باشد.")

        return super().validate(attrs)

    def create(self, validated_data):
        teammates = validated_data.pop("teammates", [])
        validated_data["create_date"] = datetime.datetime.now()
        team = models.Team.objects.create(**validated_data)
        if teammates:
            for teammate in teammates:
                models.TeamRequest.objects.create(
                    team=team, user=teammate["user"], user_role=teammate["user_role"], status="A"
                )
        return team

    def update(self, instance, validated_data):
        teammates = validated_data.pop("teammates", [])
        if teammates:
            models.TeamRequest.objects.filter(team=instance).delete()
            for teammate in teammates:
                models.TeamRequest.objects.create(
                    team=instance, user=teammate["user"], user_role=teammate["user_role"], status="A"
                )
        return super().update(instance, validated_data)


# class UserInfoSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ["id", "full_name", "avatar"]

#     def to_representation(self, instance: User):
#         team_request = models.TeamRequest.objects.filter(user=instance, status="A").first()
#         rep = super().to_representation(instance)
#         rep["has_team"] = {"id": team_request.team.id, "title": team_request.team.title} if team_request else None
#         rep["avatar"] = instance.avatar.url if instance.avatar else None
#         rep["resume_id"] = instance.resume.id if instance.resume else None
#         return rep
