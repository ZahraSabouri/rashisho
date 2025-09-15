from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.api.permissions import IsUser, IsSysgod
from apps.project.models import TeamBuildingAnnouncement
from apps.project.api.serializers.team_announcements import TeamBuildingAnnouncementSerializer


class TeamBuildingAnnouncementsView(APIView):
    permission_classes = [IsUser | IsSysgod]
    
    def get(self, request):
        announcements = TeamBuildingAnnouncement.objects.filter(
            is_active=True
        ).prefetch_related('video_buttons')
        
        serializer = TeamBuildingAnnouncementSerializer(announcements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TeamBuildingRulesView(APIView):    
    permission_classes = [IsUser | IsSysgod]
    
    def get(self, request):
        user = request.user
        
        # Get user's current team info if any
        from apps.project.models import TeamRequest
        user_membership = TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).select_related('team').first()
        
        rules_data = {
            'team_size_limits': {
                'min_members': 2,  # Could be configurable via admin
                'max_members': 6   # Could be configurable via admin
            },
            'user_specific_rules': {}
        }
        
        if user_membership:
            team = user_membership.team
            current_members = TeamRequest.objects.filter(
                team=team, status='A', request_type='JOIN'
            ).count()
            
            pending_invites = TeamRequest.objects.filter(
                team=team, status='W', request_type='INVITE'
            ).count()
            
            remaining_spots = team.count - current_members
            max_invites = remaining_spots - pending_invites
            
            rules_data['user_specific_rules'] = {
                'current_team': {
                    'id': team.id,
                    'title': team.title,
                    'current_members': current_members,
                    'max_members': team.count,
                    'remaining_spots': remaining_spots,
                    'pending_invites': pending_invites,
                    'can_send_invites': max_invites,
                    'is_leader': user_membership.user_role == 'C'
                },
                'invitation_rules': {
                    'max_active_invites': max(0, max_invites),
                    'rule_description': f"شما فقط به تعداد {remaining_spots} نفر باقی‌مانده از حداکثر می‌توانید درخواست عضویت بفرستید."
                }
            }
        
        return Response(rules_data, status=status.HTTP_200_OK)

