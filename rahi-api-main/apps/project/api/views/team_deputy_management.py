from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth import get_user_model

from apps.project import models

class TeamDeputyManagementViewSet:
    @action(methods=['POST'], detail=False, url_path='promote-deputy')
    def promote_member_to_deputy(self, request):
 
        user = request.user
        member_id = request.data.get('member_id')
        
        if not member_id:
            raise ValidationError("شناسه عضو الزامی است")
        
        # Check if user is team leader
        leadership = models.TeamRequest.objects.filter(
            user=user, status='A', user_role='C', request_type='JOIN'
        ).first()
        
        if not leadership:
            raise ValidationError("فقط سرگروه می‌تواند قائم مقام تعیین کند")
        
        team = leadership.team
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            member_user = User.objects.get(id=member_id)
            team.promote_to_deputy(member_user, user)
            
            return Response({
                "message": f"{member_user.full_name} به قائم مقام تیم ارتقا یافت",
                "deputy": {
                    "id": member_user.id,
                    "full_name": member_user.full_name,
                    "role": "قائم مقام"
                }
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            raise ValidationError("کاربر یافت نشد")
        except ValueError as e:
            raise ValidationError(str(e))
    
    @action(methods=['POST'], detail=False, url_path='demote-deputy')
    def demote_deputy_to_member(self, request):
        user = request.user
        
        # Check if user is team leader
        leadership = models.TeamRequest.objects.filter(
            user=user, status='A', user_role='C', request_type='JOIN'
        ).first()
        
        if not leadership:
            raise ValidationError("فقط سرگروه می‌تواند قائم مقام را تنزل دهد")
        
        team = leadership.team
        
        try:
            deputy_user = team.get_deputy_user()
            if not deputy_user:
                raise ValidationError("این تیم قائم مقام ندارد")
            
            team.demote_deputy(user)
            
            return Response({
                "message": f"{deputy_user.full_name} از قائم مقامی تنزل یافت",
                "former_deputy": {
                    "id": deputy_user.id,
                    "full_name": deputy_user.full_name,
                    "role": "عضو"
                }
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            raise ValidationError(str(e))
    
    @action(methods=['GET'], detail=False, url_path='leadership-info')
    def get_leadership_info(self, request):
        user = request.user
        
        membership = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).first()
        
        if not membership:
            raise ValidationError("شما عضو هیچ تیمی نیستید")
        
        team = membership.team
        leadership = team.get_leadership()
        
        leadership_data = []
        for leader in leadership:
            leadership_data.append({
                'id': leader.user.id,
                'full_name': leader.user.full_name,
                'avatar': leader.user.avatar.url if leader.user.avatar else None,
                'role': leader.user_role,
                'role_display': leader.get_user_role_display(),
                'is_current_user': leader.user == user,
                'can_manage_team': True
            })
        
        return Response({
            "team_id": team.id,
            "team_title": team.title,
            "team_code": team.team_code,
            "leadership": leadership_data,
            "user_can_manage": team.can_user_manage_team(user)
        })