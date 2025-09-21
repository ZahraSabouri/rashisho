from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ValidationError

from apps.api.permissions import IsUser, IsSysgod
from apps.project import models
from apps.project.api.serializers import team as team_serializers
from apps.project.api.views.team_deputy_management import TeamDeputyManagementViewSet


class TeamRequestViewSet(TeamDeputyManagementViewSet, ModelViewSet):
    serializer_class = team_serializers.TeamRequestSerializer
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        user = self.request.user
        request_type = self.request.query_params.get('request_type')
        status_filter = self.request.query_params.get('status')
        
        queryset = models.TeamRequest.objects.all()
        
        # Filter by request type if specified
        if request_type:
            queryset = queryset.filter(request_type=request_type)
        
        # Filter by status if specified
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset.select_related('user', 'team', 'requested_by')

    @action(methods=['POST'], detail=False, url_path='request-leave')
    def request_leave_team(self, request):
        user = request.user
        
        # Check if user is in a team
        membership = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).first()
        
        if not membership:
            raise ValidationError("شما عضو هیچ تیمی نیستید!")
        
        if membership.user_role == 'C':
            raise ValidationError("سرگروه نمی‌تواند تیم را ترک کند! باید تیم را منحل کند.")
        
        # Check for existing pending leave request
        existing_leave_request = models.TeamRequest.objects.filter(
            user=user, team=membership.team, request_type='LEAVE', status='W'
        ).first()
        
        if existing_leave_request:
            raise ValidationError("درخواست خروج شما در حال بررسی است!")
        
        # Create leave request
        leave_request = models.TeamRequest.objects.create(
            team=membership.team,
            user=user,
            request_type='LEAVE',
            user_role=membership.user_role,
            status='W',
            requested_by=user,
            description=request.data.get('description', '')
        )
        
        serializer = self.get_serializer(leave_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=False, url_path='cancel-leave')
    def cancel_leave_request(self, request):
        user = request.user
        
        leave_request = models.TeamRequest.objects.filter(
            user=user, request_type='LEAVE', status='W'
        ).first()
        
        if not leave_request:
            raise ValidationError("درخواست خروجی برای لغو وجود ندارد!")
        
        leave_request.delete()
        return Response({"message": "درخواست خروج لغو شد."}, status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=False, url_path='approve-leave')
    def approve_leave_request(self, request):
        user = request.user
        request_id = request.data.get('request_id')
        action_type = request.data.get('action')  # 'approve' or 'reject'
        
        if not request_id or action_type not in ['approve', 'reject']:
            raise ValidationError("پارامترهای نامعتبر!")
        
        leave_request = models.TeamRequest.objects.filter(
            id=request_id, request_type='LEAVE', status='W'
        ).first()
        
        if not leave_request:
            raise ValidationError("درخواست خروج یافت نشد!")
        
        # Check if current user is team leader
        leader_membership = models.TeamRequest.objects.filter(
            user=user, team=leave_request.team, status='A', user_role='C'
        ).first()
        
        if not leader_membership:
            raise ValidationError("فقط سرگروه می‌تواند درخواست‌ها را بررسی کند!")
        
        with transaction.atomic():
            if action_type == 'approve':
                # Approve leave request
                leave_request.status = 'A'
                leave_request.save()
                
                # Remove user from team (update their membership status)
                membership = models.TeamRequest.objects.filter(
                    user=leave_request.user, team=leave_request.team, 
                    status='A', request_type='JOIN'
                ).first()
                
                if membership:
                    membership.status = 'R'  # Mark as removed
                    membership.save()
                
                # Check if team dissolution can complete
                if leave_request.team.is_dissolution_in_progress and leave_request.team.can_dissolve():
                    leave_request.team.delete()
                    return Response({"message": "عضو از تیم خارج شد و تیم منحل شد."}, status=status.HTTP_200_OK)
                
                return Response({"message": "درخواست خروج تأیید شد."}, status=status.HTTP_200_OK)
            
            else:  # reject
                leave_request.status = 'R'
                leave_request.save()
                return Response({"message": "درخواست خروج رد شد."}, status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=False, url_path='dissolve-team')
    def request_team_dissolution(self, request):
        user = request.user
        
        # Check if user is team leader
        leadership = models.TeamRequest.objects.filter(
            user=user, status='A', user_role='C'
        ).first()
        
        if not leadership:
            raise ValidationError("شما سرگروه هیچ تیمی نیستید!")
        
        team = leadership.team
        
        if team.is_dissolution_in_progress:
            raise ValidationError("درخواست انحلال این تیم در حال بررسی است!")
        
        with transaction.atomic():
            # Mark team for dissolution
            team.dissolution_requested_by = user
            team.dissolution_requested_at = timezone.now()
            team.is_dissolution_in_progress = True
            team.save()
            
            # Auto-create leave requests for all members (except leader)
            members = models.TeamRequest.objects.filter(
                team=team, status='A', request_type='JOIN'
            ).exclude(user_role='C')
            
            for member in members:
                models.TeamRequest.objects.get_or_create(
                    team=team,
                    user=member.user,
                    request_type='LEAVE',
                    defaults={
                        'user_role': member.user_role,
                        'status': 'W',
                        'requested_by': user,
                        'description': 'درخواست خودکار در پی انحلال تیم'
                    }
                )
        
        return Response({
            "message": "درخواست انحلال تیم ارسال شد. منتظر تأیید اعضا باشید.",
            "auto_leave_requests_created": members.count()
        }, status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=False, url_path='cancel-dissolution')
    def cancel_team_dissolution(self, request):
        user = request.user
        
        # Check if user is team leader
        leadership = models.TeamRequest.objects.filter(
            user=user, status='A', user_role='C'
        ).first()
        
        if not leadership:
            raise ValidationError("شما سرگروه هیچ تیمی نیستید!")
        
        team = leadership.team
        
        if not team.is_dissolution_in_progress:
            raise ValidationError("هیچ درخواست انحلالی در جریان نیست!")
        
        with transaction.atomic():
            # Cancel dissolution
            team.dissolution_requested_by = None
            team.dissolution_requested_at = None
            team.is_dissolution_in_progress = False
            team.save()
            
            # Remove all pending leave requests created for dissolution
            pending_leaves = models.TeamRequest.objects.filter(
                team=team, request_type='LEAVE', status='W', requested_by=user
            )
            
            count = pending_leaves.count()
            pending_leaves.delete()
        
        return Response({
            "message": "درخواست انحلال تیم لغو شد.",
            "cancelled_leave_requests": count
        }, status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path='my-requests')
    def get_my_requests(self, request):
        user = request.user
        
        # Requests made by user
        my_requests = models.TeamRequest.objects.filter(
            user=user, status='W'
        ).select_related('team', 'requested_by')
        
        # Requests for user to approve (if they're team leader)
        leader_teams = models.TeamRequest.objects.filter(
            user=user, status='A', user_role='C'
        ).values_list('team', flat=True)
        
        requests_to_approve = models.TeamRequest.objects.filter(
            team__in=leader_teams, status='W'
        ).exclude(user=user).select_related('user', 'team', 'requested_by')
        
        return Response({
            "my_requests": team_serializers.TeamRequestSerializer(
                my_requests, many=True, context={'request': request}
            ).data,
            "requests_to_approve": team_serializers.TeamRequestSerializer(
                requests_to_approve, many=True, context={'request': request}
            ).data
        })


class TeamEnhancedViewSet(ModelViewSet):
    serializer_class = team_serializers.TeamSerializer
    queryset = models.Team.objects.all()
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        """Filter teams based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by formation status
        formation_status = self.request.query_params.get('formation_status')
        if formation_status == 'formed':
            # Teams with enough members
            queryset = queryset.filter(
                requests__status='A'
            ).distinct().annotate(
                member_count=models.Count('requests', filter=models.Q(requests__status='A'))
            ).filter(member_count__gte=2)
        
        elif formation_status == 'forming':
            # Teams still looking for members
            queryset = queryset.filter(
                requests__status='A'
            ).distinct().annotate(
                member_count=models.Count('requests', filter=models.Q(requests__status='A'))
            ).filter(member_count__lt=models.F('count'))
        
        return queryset.select_related('project')

    @action(methods=['GET'], detail=True, url_path='members')
    def get_team_members(self, request, pk=None):
        """Get detailed team member information"""
        team = self.get_object()
        
        members = models.TeamRequest.objects.filter(
            team=team, status='A', request_type='JOIN'
        ).select_related('user')
        
        member_data = []
        for member in members:
            member_data.append({
                'id': member.user.id,
                'full_name': member.user.full_name,
                'avatar': member.user.avatar.url if member.user.avatar else None,
                'user_role': member.get_user_role_display(),
                'is_leader': member.user_role == 'C',
                'joined_at': member.created_at
            })
        
        return Response(member_data)

    @action(methods=['GET'], detail=False, url_path='my-team')
    def get_my_team(self, request):
        user = request.user
        
        membership = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).select_related('team').first()
        
        if not membership:
            return Response({"message": "شما عضو هیچ تیمی نیستید!"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(membership.team, context={'request': request})
        return Response(serializer.data)