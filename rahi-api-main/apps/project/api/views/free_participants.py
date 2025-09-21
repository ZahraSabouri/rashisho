from django.db.models import Count, Q, F, Exists, OuterRef
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsUser, IsSysgod
from apps.project import models
from apps.project.api.serializers.free_participants import (
    FreeParticipantSerializer, FreeParticipantDetailSerializer
)
from apps.settings.models import Province

User = get_user_model()


class FreeParticipantsViewSet(ModelViewSet):
    """
    API for managing free participants (users without teams)
    Supports two modes as per requirements:
    - Mode 1: Dropdown "My Attractive Projects" 
    - Mode 2: List appears below profile
    """
    serializer_class = FreeParticipantSerializer
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        # Get users who don't have active team memberships
        queryset = User.objects.exclude(
            team_requests__status='A',
            team_requests__request_type='JOIN'
        ).select_related(
            'resume', 'city'
        ).prefetch_related(
            'attractiveness_declarations__project',
            'resume__educations'
        )
        
        # Apply filters
        return self._apply_filters(queryset)
    
    def _apply_filters(self, queryset):
        """Apply various filters based on request parameters"""
        request = self.request
        
        # Filter by study field
        study_field = request.query_params.get('study_field')
        if study_field:
            queryset = queryset.filter(
                resume__educations__field_of_study__icontains=study_field
            )
        
        # Filter by degree level
        degree_level = request.query_params.get('degree_level')
        if degree_level:
            queryset = queryset.filter(
                resume__educations__degree_level=degree_level
            )
        
        # Filter by attractive project
        attractive_project_id = request.query_params.get('attractive_project')
        if attractive_project_id:
            queryset = queryset.filter(
                attractiveness_declarations__project_id=attractive_project_id
            )
        
        # Filter by province (team formation province)
        province_id = request.query_params.get('province')
        if province_id:
            queryset = queryset.filter(
                Q(resume__team_formation_province_id=province_id) |
                Q(city__province_id=province_id)  # Fallback to user's city province
            )
        
        # Search by name
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                full_name__icontains=search
            )
        
        return queryset.distinct()
    
    def list(self, request, *args, **kwargs):
        """
        List free participants with smart ordering:
        1. Shared project attraction (with current user)
        2. Alphabetically
        3. Other criteria
        """
        queryset = self.get_queryset()
        
        # Get current user's attractive projects for smart ordering
        user_attractive_projects = []
        if request.user.is_authenticated:
            user_attractive_projects = list(
                request.user.attractiveness_declarations.values_list(
                    'project_id', flat=True
                )
            )
        
        # Order by shared attractions first, then alphabetically
        if user_attractive_projects:
            queryset = queryset.annotate(
                shared_attractions=Count(
                    'attractiveness_declarations',
                    filter=Q(attractiveness_declarations__project_id__in=user_attractive_projects)
                )
            ).order_by('-shared_attractions', 'full_name')
        else:
            queryset = queryset.order_by('full_name')
        
        # Pagination
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        offset = (page - 1) * page_size
        
        total_count = queryset.count()
        participants = queryset[offset:offset + page_size]
        
        # Use detailed serializer for better information
        serializer = FreeParticipantDetailSerializer(
            participants, many=True, context={'request': request}
        )
        
        return Response({
            'participants': serializer.data,
            'pagination': {
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'has_more': offset + page_size < total_count
            },
            'user_context': self._get_user_context(request.user)
        }, status=status.HTTP_200_OK)
    
    def _get_user_context(self, user):
        """Get context about current user for determining available actions"""
        if not user.is_authenticated:
            return {'is_authenticated': False}
        
        # Check user's team status
        user_membership = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).select_related('team').first()
        
        context = {
            'is_authenticated': True,
            'has_team': bool(user_membership),
            'is_team_leader': False,
            'can_invite': False,
            'can_propose': True,  # Everyone can propose team formation
        }
        
        if user_membership:
            context.update({
                'team_id': user_membership.team.id,
                'team_code': user_membership.team.team_code,
                'user_role': user_membership.user_role,
                'is_team_leader': user_membership.user_role == 'C',
                'is_deputy': user_membership.user_role == 'D',
                'can_invite': user_membership.user_role in ['C', 'D'],  # Leaders and deputies can invite
            })
        
        return context
    
    @action(methods=['GET'], detail=False, url_path='filters')
    def get_available_filters(self, request):
        """Get available filter options for free participants"""
        # Get unique study fields from free participants
        free_users = self.get_queryset()
        
        study_fields = free_users.filter(
            resume__educations__isnull=False
        ).values_list(
            'resume__educations__field_of_study', flat=True
        ).distinct()[:50]
        
        # Get degree levels
        degree_levels = free_users.filter(
            resume__educations__isnull=False
        ).values_list(
            'resume__educations__degree_level', flat=True
        ).distinct()
        
        # Get attractive projects that free participants have
        attractive_projects = models.Project.objects.filter(
            attractiveness_declarations__user__in=free_users
        ).distinct().values('id', 'title')[:50]
        
        # Get provinces
        provinces = Province.objects.filter(
            Q(team_formation_resumes__user__in=free_users) |
            Q(cities__users__in=free_users)
        ).distinct().values('id', 'title')
        
        return Response({
            'study_fields': [{'value': field, 'label': field} for field in study_fields if field],
            'degree_levels': [{'value': level, 'label': level} for level in degree_levels if level],
            'attractive_projects': list(attractive_projects),
            'provinces': list(provinces)
        }, status=status.HTTP_200_OK)
    
    @action(methods=['GET'], detail=True, url_path='actions')
    def get_user_actions(self, request, pk=None):
        """
        Get available actions for a specific free participant
        Based on current user's team status:
        - Team leader: can invite or propose
        - Team member: can only propose
        - No team: can only propose
        """
        try:
            participant = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {'error': 'کاربر یافت نشد'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        current_user = request.user
        user_context = self._get_user_context(current_user)
        
        available_actions = []
        
        if user_context['is_authenticated']:
            # Always can propose team formation
            available_actions.append({
                'action': 'propose_team',
                'label': 'پیشنهاد تشکیل تیم',
                'description': 'پیشنهاد تشکیل تیم جدید با این شخص'
            })
            
            # If user is team leader or deputy, can invite
            if user_context['can_invite']:
                # Check team capacity and validation
                user_membership = models.TeamRequest.objects.filter(
                    user=current_user, status='A', request_type='JOIN'
                ).select_related('team').first()
                
                if user_membership:
                    team = user_membership.team
                    current_members = team.get_member_count()
                    
                    # Check capacity
                    stage_settings = team.get_stage_settings().filter(
                        control_type='formation'
                    ).first()
                    max_size = stage_settings.max_team_size if stage_settings else 6
                    
                    if current_members < max_size:
                        # Check repeat teammate rules
                        can_invite, reason = team.can_invite_user(current_user, participant)
                        
                        if can_invite:
                            available_actions.append({
                                'action': 'invite_to_team',
                                'label': 'دعوت به تیم',
                                'description': f'دعوت به تیم {team.title}',
                                'team_info': {
                                    'team_id': team.id,
                                    'team_code': team.team_code,
                                    'current_members': current_members,
                                    'max_members': max_size
                                }
                            })
                        else:
                            available_actions.append({
                                'action': 'invite_blocked',
                                'label': 'دعوت امکان‌پذیر نیست',
                                'description': reason,
                                'blocked': True
                            })
        
        return Response({
            'participant_id': participant.id,
            'participant_name': participant.full_name,
            'available_actions': available_actions,
            'user_context': user_context
        }, status=status.HTTP_200_OK)
    
    @action(methods=['GET'], detail=False, url_path='attractive-projects-modes')
    def get_attractive_projects_modes(self, request):
        """
        Get attractive projects in both modes:
        Mode 1: Dropdown format
        Mode 2: Expanded list format
        """
        user = request.user
        if not user.is_authenticated:
            return Response(
                {'error': 'وارد سیستم شوید'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get user's attractive projects
        attractive_projects = user.attractiveness_declarations.select_related(
            'project'
        ).order_by('project__title')
        
        # Mode 1: Simple dropdown format
        mode_1_data = [
            {
                'id': decl.project.id,
                'title': decl.project.title,
                'short_description': decl.project.description[:100] + '...' if len(decl.project.description) > 100 else decl.project.description
            }
            for decl in attractive_projects
        ]
        
        # Mode 2: Detailed expanded format
        mode_2_data = []
        for decl in attractive_projects:
            project = decl.project
            
            # Get free participants interested in this project
            interested_participants = User.objects.filter(
                attractiveness_declarations__project=project
            ).exclude(
                team_requests__status='A',
                team_requests__request_type='JOIN'
            ).exclude(id=user.id)[:10]  # Limit to 10 for performance
            
            mode_2_data.append({
                'id': project.id,
                'title': project.title,
                'description': project.description,
                'interested_participants_count': interested_participants.count(),
                'sample_participants': FreeParticipantSerializer(
                    interested_participants, many=True, context={'request': request}
                ).data
            })
        
        return Response({
            'mode_1': mode_1_data,
            'mode_2': mode_2_data,
            'total_attractive_projects': attractive_projects.count()
        }, status=status.HTTP_200_OK)