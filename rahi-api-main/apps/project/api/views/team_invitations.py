from django.db.models import Q, Count, Exists, OuterRef
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ValidationError

from apps.api.permissions import IsUser, IsSysgod
from apps.project import models
from apps.account.api.serializers.user import UserBriefInfoSerializer
from apps.project.api.serializers import team as team_serializers
from apps.project.api.serializers.team import TeamRequestSerializer
from apps.settings.models import StudyField, Province
from apps.resume.models import Resume
from apps.project.models import Team, TeamRequest

User = get_user_model()


class TeamInvitationViewSet(ModelViewSet):    
    serializer_class = team_serializers.TeamRequestSerializer
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        return models.TeamRequest.objects.filter(
            request_type__in=['INVITE', 'PROPOSE']
        ).select_related('user', 'team', 'requested_by')

    @action(methods=['POST'], detail=False, url_path='invite-user')
    def invite_user_to_team(self, request):
        user = request.user
        target_user_id = request.data.get('user_id')
        message = request.data.get('message', '')
        
        if not target_user_id:
            raise ValidationError("شناسه کاربر مقصد الزامی است!")
        
        # Check if current user is team leader
        leadership = models.TeamRequest.objects.filter(
            user=user, status='A', user_role='C', request_type='JOIN'
        ).first()
        
        if not leadership:
            raise ValidationError("فقط سرگروه‌ها می‌توانند دعوت کنند!")
        
        team = leadership.team
        
        # Enhanced team capacity validation
        current_members = models.TeamRequest.objects.filter(
            team=team, status='A', request_type='JOIN'
        ).count()
        
        pending_invites = models.TeamRequest.objects.filter(
            team=team, status='W', request_type='INVITE'
        ).count()
        
        total_committed = current_members + pending_invites
        
        if total_committed >= team.count:
            raise ValidationError(
                f"تیم پر است! اعضای فعلی: {current_members}، دعوت‌های در انتظار: {pending_invites}، "
                f"حداکثر مجاز: {team.count}"
            )
        
        remaining_spots = team.count - total_committed
        
        if remaining_spots <= 0:
            raise ValidationError(
                f"شما فقط به تعداد {team.count - current_members} نفر باقی‌مانده از حداکثر می‌توانید "
                f"درخواست عضویت بفرستید. در حال حاضر {pending_invites} درخواست فعال دارید."
            )
        
        # Get target user
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            raise ValidationError("کاربر مقصد یافت نشد!")
        
        # Check if target user is free (not in any team)
        existing_membership = models.TeamRequest.objects.filter(
            user=target_user, status='A', request_type='JOIN'
        ).first()
        
        if existing_membership:
            raise ValidationError("این کاربر عضو تیمی است!")
        
        # Check for existing pending invitation
        existing_invite = models.TeamRequest.objects.filter(
            team=team, user=target_user, request_type='INVITE', status='W'
        ).first()
        
        if existing_invite:
            raise ValidationError("دعوت قبلی در انتظار پاسخ است!")
        
        # Create invitation
        invitation = models.TeamRequest.objects.create(
            team=team,
            user=target_user,
            request_type='INVITE',
            user_role='M',
            status='W',
            requested_by=user,
            description=message
        )
        
        serializer = self.get_serializer(invitation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=False, url_path='propose-team')
    def propose_team_formation(self, request):
        user = request.user
        target_user_id = request.data.get('user_id')
        message = request.data.get('message', '')
        
        if not target_user_id:
            raise ValidationError("شناسه کاربر مقصد الزامی است!")
        
        # Check if user is in a team (leader or member)
        user_team = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).first()
        
        if not user_team:
            raise ValidationError("شما عضو هیچ تیمی نیستید!")
        
        team = user_team.team
        
        # Get target user
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            raise ValidationError("کاربر مقصد یافت نشد!")
        
        # Check if target user is free
        existing_membership = models.TeamRequest.objects.filter(
            user=target_user, status='A', request_type='JOIN'
        ).first()
        
        if existing_membership:
            raise ValidationError("این کاربر عضو تیمی است!")
        
        # Check for existing proposal
        existing_proposal = models.TeamRequest.objects.filter(
            team=team, user=target_user, request_type='PROPOSE', status='W'
        ).first()
        
        if existing_proposal:
            raise ValidationError("پیشنهاد قبلی در انتظار بررسی است!")
        
        # Create proposal
        proposal = models.TeamRequest.objects.create(
            team=team,
            user=target_user,
            request_type='PROPOSE',
            user_role='M',
            status='W',
            requested_by=user,  # Who made the proposal
            description=message
        )
        
        serializer = self.get_serializer(proposal)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=False, url_path='respond-invitation')
    def respond_to_invitation(self, request):
        user = request.user
        invitation_id = request.data.get('invitation_id')
        response_action = request.data.get('action')  # 'accept' or 'reject'
        
        if not invitation_id or response_action not in ['accept', 'reject']:
            raise ValidationError("پارامترهای نامعتبر!")
        
        # Get invitation
        invitation = models.TeamRequest.objects.filter(
            id=invitation_id, user=user, request_type='INVITE', status='W'
        ).first()
        
        if not invitation:
            raise ValidationError("دعوت یافت نشد!")
        
        # Check if user is still free
        if response_action == 'accept':
            existing_membership = models.TeamRequest.objects.filter(
                user=user, status='A', request_type='JOIN'
            ).first()
            
            if existing_membership:
                raise ValidationError("شما عضو تیمی هستید!")
        
        if response_action == 'accept':
            # Accept invitation - create membership
            invitation.status = 'A'
            invitation.save()
            
            # Create actual membership
            models.TeamRequest.objects.create(
                team=invitation.team,
                user=user,
                request_type='JOIN',
                user_role='M',
                status='A',
                requested_by=user
            )
            
            message = f"به تیم {invitation.team.title} پیوستید!"
            
        else:  # reject
            invitation.status = 'R'
            invitation.save()
            message = "دعوت رد شد."
        
        return Response({"message": message}, status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path='my-invitations')
    def get_my_invitations(self, request):
        user = request.user
        
        # Invitations received by user
        received_invitations = models.TeamRequest.objects.filter(
            user=user, request_type='INVITE', status='W'
        ).select_related('team', 'requested_by')
        
        # Proposals about user (for team leaders to see)
        user_teams = models.TeamRequest.objects.filter(
            user=user, status='A', user_role='C', request_type='JOIN'
        ).values_list('team', flat=True)
        
        proposals_to_review = models.TeamRequest.objects.filter(
            team__in=user_teams, request_type='PROPOSE', status='W'
        ).select_related('user', 'requested_by', 'team')
        
        return Response({
            "received_invitations": team_serializers.TeamRequestSerializer(
                received_invitations, many=True, context={'request': request}
            ).data,
            "proposals_to_review": team_serializers.TeamRequestSerializer(
                proposals_to_review, many=True, context={'request': request}
            ).data
        })


class EnhancedTeamInvitationViewSet(ModelViewSet):
# class TeamInvitationViewSet(ModelViewSet):
    serializer_class = TeamRequestSerializer
    permission_classes = [IsUser | IsSysgod]
    
    @action(methods=['POST'], detail=False, url_path='invite-with-validation')
    def invite_user_with_validation(self, request):
        inviter = request.user
        target_user_id = request.data.get('user_id')
        team_id = request.data.get('team_id')
        
        if not target_user_id or not team_id:
            return Response(
                {'error': 'user_id و team_id الزامی است'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            target_user = User.objects.get(id=target_user_id)
            team = Team.objects.get(id=team_id)
        except (User.DoesNotExist, Team.DoesNotExist):
            return Response(
                {'error': 'کاربر یا تیم پیدا نشد'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify inviter is team leader or deputy
        inviter_membership = team.requests.filter(
            user=inviter, 
            status='A', 
            user_role__in=['C', 'D'],
            request_type='JOIN'
        ).first()
        
        if not inviter_membership:
            return Response(
                {'error': 'فقط سرگروه یا قائم مقام می‌تواند دعوت کند'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if target user is already in a team
        existing_membership = TeamRequest.objects.filter(
            user=target_user,
            status='A',
            request_type='JOIN'
        ).first()
        
        if existing_membership:
            return Response(
                {'error': 'این کاربر قبلاً عضو تیمی است'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check team capacity
        current_members = team.get_member_count()
        stage_settings = team.get_stage_settings().filter(control_type='formation').first()
        max_size = stage_settings.max_team_size if stage_settings else 6
        
        if current_members >= max_size:
            return Response(
                {'error': 'تیم به حداکثر ظرفیت رسیده است'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check pending invitations
        pending_invites = team.requests.filter(status='W', request_type='INVITE').count()
        remaining_spots = max_size - current_members
        
        if pending_invites >= remaining_spots:
            return Response(
                {'error': 'تعداد دعوت‌های در انتظار از ظرفیت باقی‌مانده بیشتر است'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check repeat teammate prevention rule
        can_invite, reason = team.can_invite_user(inviter, target_user)
        
        if not can_invite:
            return Response({
                'error': reason,
                'error_type': 'repeat_teammate_prevention',
                'suggestion': 'لطفاً شرکت‌کنندگان جدید را برای تیم‌سازی در نظر بگیرید'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if invitation already exists
        existing_invitation = TeamRequest.objects.filter(
            team=team,
            user=target_user,
            request_type='INVITE',
            status='W'
        ).first()
        
        if existing_invitation:
            return Response(
                {'error': 'دعوت‌نامه قبلاً ارسال شده است'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create invitation
        invitation = TeamRequest.objects.create(
            team=team,
            user=target_user,
            user_role='M',
            request_type='INVITE',
            status='W',
            requested_by=inviter,
            description=request.data.get('description', '')
        )
        
        return Response({
            'message': 'دعوت‌نامه با موفقیت ارسال شد',
            'invitation': TeamRequestSerializer(invitation, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)
    
    @action(methods=['GET'], detail=False, url_path='available-users')
    def get_available_users(self, request):
        """
        Get users available for invitation (considering repeat teammate rules)
        """
        user = request.user
        
        # Get user's current team
        user_membership = TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).select_related('team').first()
        
        if not user_membership or user_membership.user_role not in ['C', 'D']:
            return Response(
                {'error': 'شما مجاز به مشاهده این اطلاعات نیستید'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        team = user_membership.team
        
        # Get all users who don't have a team
        users_without_team = User.objects.exclude(
            team_requests__status='A',
            team_requests__request_type='JOIN'
        )
        
        # Check if repeat prevention is enabled
        stage_settings = team.get_stage_settings().filter(
            prevent_repeat_teammates=True
        ).first()
        
        if stage_settings:
            # Get previous teammates
            previous_teammate_teams = TeamRequest.objects.filter(
                user=user,
                status='A',
                request_type='JOIN'
            ).values_list('team_id', flat=True)
            
            previous_teammate_ids = TeamRequest.objects.filter(
                team_id__in=previous_teammate_teams,
                status='A',
                request_type='JOIN'
            ).exclude(user=user).values_list('user_id', flat=True)
            
            # Separate new users from previous teammates
            new_users = users_without_team.exclude(id__in=previous_teammate_ids)
            previous_teammates = users_without_team.filter(id__in=previous_teammate_ids)
            
            # If there are new users available, don't show previous teammates
            if new_users.exists():
                available_users = new_users
                blocked_users = previous_teammates
                show_blocked_reason = True
            else:
                available_users = users_without_team
                blocked_users = User.objects.none()
                show_blocked_reason = False
        else:
            available_users = users_without_team
            blocked_users = User.objects.none()
            show_blocked_reason = False
        
        # Apply filters
        search = request.query_params.get('search', '')
        if search:
            available_users = available_users.filter(
                full_name__icontains=search
            )
            blocked_users = blocked_users.filter(
                full_name__icontains=search
            )
        
        return Response({
            'available_users': UserBriefInfoSerializer(
                available_users[:50], many=True, context={'request': request}
            ).data,
            'blocked_users': UserBriefInfoSerializer(
                blocked_users[:20], many=True, context={'request': request}
            ).data if show_blocked_reason else [],
            'repeat_prevention_enabled': bool(stage_settings),
            'blocked_reason': (
                'این افراد قبلاً همتیم شما بوده‌اند و شرکت‌کنندگان جدید در دسترس است' 
                if show_blocked_reason else None
            )
        }, status=status.HTTP_200_OK)
    
    @action(methods=['POST'], detail=False, url_path='check-invitation-validity')
    def check_invitation_validity(self, request):
        """
        Check if a potential invitation is valid before sending
        """
        inviter = request.user
        target_user_id = request.data.get('user_id')
        team_id = request.data.get('team_id')
        
        if not target_user_id or not team_id:
            return Response(
                {'valid': False, 'reason': 'اطلاعات کاربر یا تیم ناقص است'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            target_user = User.objects.get(id=target_user_id)
            team = Team.objects.get(id=team_id)
        except (User.DoesNotExist, Team.DoesNotExist):
            return Response(
                {'valid': False, 'reason': 'کاربر یا تیم پیدا نشد'}, 
                status=status.HTTP_200_OK
            )
        
        # All validation checks
        can_invite, reason = team.can_invite_user(inviter, target_user)
        
        return Response({
            'valid': can_invite,
            'reason': reason if not can_invite else 'دعوت قابل ارسال است',
            'user_info': {
                'name': target_user.full_name,
                'has_been_teammate': (
                    team._have_been_teammates(inviter, target_user) 
                    if can_invite else None
                )
            }
        }, status=status.HTTP_200_OK)


class FreeParticipantsViewSet(ModelViewSet):    
    serializer_class = team_serializers.UserTeamInfoSerializer
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        # Base queryset: users without active team membership
        free_users = User.objects.filter(
            ~Exists(
                models.TeamRequest.objects.filter(
                    user=OuterRef('pk'), 
                    status='A', 
                    request_type='JOIN'
                )
            )
        ).select_related('city', 'resume')
        
        # Apply filters
        study_field = self.request.query_params.get('study_field')
        if study_field:
            free_users = free_users.filter(
                resume__educations__field__id=study_field
            )
        
        degree_level = self.request.query_params.get('degree_level')
        if degree_level:
            free_users = free_users.filter(
                resume__educations__degree=degree_level
            )
        
        attractive_project = self.request.query_params.get('attractive_project')
        if attractive_project:
            free_users = free_users.filter(
                project_attractions__project__id=attractive_project
            )
        
        province = self.request.query_params.get('province')
        if province:
            # Filter by team formation province from resume
            free_users = free_users.filter(
                Q(resume__team_formation_province__id=province) |
                Q(city__province__id=province)  # Fallback to residence province
            )
        
        return free_users.distinct()
    
    def list(self, request):
        queryset = self.get_queryset()
        current_user = request.user
        
        # Get current user's attractive projects for similarity scoring
        user_attractions = list(
            models.ProjectAttractiveness.objects.filter(
                user=current_user
            ).values_list('project_id', flat=True)
        )
        
        # Calculate shared attractions and order
        participants = []
        for user in queryset:
            user_attractions_list = list(
                models.ProjectAttractiveness.objects.filter(
                    user=user
                ).values_list('project_id', flat=True)
            )
            
            # Calculate shared attractions
            shared_count = len(set(user_attractions) & set(user_attractions_list))
            
            participants.append({
                'user': user,
                'shared_attractions': shared_count,
                'attractive_projects': user_attractions_list
            })
        
        # Sort by shared attractions (desc), then alphabetically
        participants.sort(
            key=lambda x: (-x['shared_attractions'], x['user'].full_name or '')
        )
        
        # Serialize
        serialized_data = []
        for participant in participants:
            serializer = self.get_serializer(participant['user'], context={'request': request})
            data = serializer.data
            data['shared_attractions_count'] = participant['shared_attractions']
            serialized_data.append(data)
        
        return Response(serialized_data)

    @action(methods=['GET'], detail=False, url_path='filters')
    def get_available_filters(self, request):
        # Study fields
        study_fields = StudyField.objects.filter(
            is_active=True
        ).values('id', 'title')
        
        # Degree levels (from resume model)
        DEGREE_CHOICES = [
            ('DIPLOMA', 'دیپلم'),
            ('ASSOCIATE', 'کاردانی'),
            ('BACHELOR', 'کارشناسی'),
            ('MASTER', 'کارشناسی ارشد'),
            ('PHD', 'دکتری'),
        ]
        
        # Provinces
        provinces = Province.objects.filter(
            is_active=True
        ).values('id', 'title')
        
        # Popular attractive projects
        popular_projects = models.Project.objects.filter(
            is_active=True, visible=True
        ).annotate(
            attraction_count=Count('project_attractions')
        ).order_by('-attraction_count')[:20].values('id', 'title')
        
        return Response({
            'study_fields': list(study_fields),
            'degree_levels': [{'value': k, 'label': v} for k, v in DEGREE_CHOICES],
            'provinces': list(provinces),
            'popular_projects': list(popular_projects)
        })

    @action(methods=['GET'], detail=False, url_path='user-actions')
    def get_user_actions(self, request):
        user = request.user
        
        # Check user's team status
        user_membership = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).first()
        
        if not user_membership:
            return Response({
                'can_invite': False,
                'can_propose': False,
                'status': 'no_team',
                'message': 'شما عضو هیچ تیمی نیستید.'
            })
        
        is_leader = user_membership.user_role == 'C'
        team = user_membership.team
        
        # Check if team has space
        current_members = models.TeamRequest.objects.filter(
            team=team, status='A', request_type='JOIN'
        ).count()
        
        team_has_space = current_members < team.count
        
        return Response({
            'can_invite': is_leader and team_has_space,
            'can_propose': True,  # All team members can propose
            'is_leader': is_leader,
            'team_has_space': team_has_space,
            'team_info': {
                'id': team.id,
                'title': team.title,
                'current_members': current_members,
                'max_members': team.count
            }
        })