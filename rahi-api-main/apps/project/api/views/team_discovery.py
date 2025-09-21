from django.db.models import Count, Q, OuterRef, Exists
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsUser, IsSysgod
from apps.project import models
from apps.project.api.serializers import team as team_serializers
from apps.settings.models import Province


# apps/project/api/views/team_discovery.py - Create new file

from django.db.models import Count, Q, F, Exists, OuterRef
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsUser, IsSysgod
from apps.project import models
from apps.project.api.serializers.team_discovery import (
    TeamDiscoverySerializer, TeamJoinOptionsSerializer
)
from apps.settings.models import Province


class TeamDiscoveryViewSet(ModelViewSet):
    """
    Team Discovery API for browsing formed and forming teams
    Supports province filtering and team page access
    """
    serializer_class = TeamDiscoverySerializer
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        # Base queryset - exclude dissolved teams
        queryset = models.Team.objects.filter(
            is_dissolution_in_progress=False
        ).select_related('project').annotate(
            member_count=Count(
                'requests',
                filter=Q(requests__status='A', requests__request_type='JOIN')
            )
        ).filter(member_count__gte=1)  # Only teams with at least 1 member
        
        return self._apply_filters(queryset)
    
    def _apply_filters(self, queryset):
        """Apply filtering logic"""
        request = self.request
        
        # Formation status filter
        formation_status = request.query_params.get('formation_status')
        if formation_status == 'formed':
            # Teams with enough members (minimum 2 for complete teams)
            queryset = queryset.filter(member_count__gte=2)
        elif formation_status == 'forming':
            # Teams still looking for members
            queryset = queryset.filter(
                member_count__lt=F('count'),  # Less than target count
                member_count__gte=1  # But at least 1 member
            )
        
        # Province filter (based on team leader's province)
        province_id = request.query_params.get('province')
        if province_id:
            queryset = queryset.filter(
                Exists(
                    models.TeamRequest.objects.filter(
                        team=OuterRef('pk'),
                        user_role='C',  # Team leader
                        status='A',
                        request_type='JOIN',
                        user__resume__team_formation_province__id=province_id
                    )
                )
            )
        elif not request.query_params.get('all_provinces', False):
            # Default: filter by user's province
            user = request.user
            if user.is_authenticated:
                user_province_id = self._get_user_province(user)
                if user_province_id:
                    queryset = queryset.filter(
                        Exists(
                            models.TeamRequest.objects.filter(
                                team=OuterRef('pk'),
                                user_role='C',
                                status='A',
                                request_type='JOIN',
                                user__resume__team_formation_province__id=user_province_id
                            )
                        )
                    )
        
        # Project filter
        project_id = request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        # Team building stage filter
        stage = request.query_params.get('stage')
        if stage:
            queryset = queryset.filter(team_building_stage=stage)
        
        # Search by team name or code
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(team_code__icontains=search)
            )
        
        return queryset
    
    def _get_user_province(self, user):
        """Get user's province for team formation"""
        resume = getattr(user, 'resume', None)
        if resume and hasattr(resume, 'team_formation_province'):
            return resume.team_formation_province.id
        elif user.city and hasattr(user.city, 'province'):
            return user.city.province.id
        return None
    
    def list(self, request, *args, **kwargs):
        """List teams with pagination and summary"""
        queryset = self.get_queryset().order_by('-created_at')
        
        # Pagination
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        offset = (page - 1) * page_size
        
        total_count = queryset.count()
        teams = queryset[offset:offset + page_size]
        
        # Get summary statistics
        total_formed = queryset.filter(member_count__gte=2).count()
        total_forming = queryset.filter(
            member_count__lt=F('count'),
            member_count__gte=1
        ).count()
        
        serializer = self.get_serializer(teams, many=True)
        
        return Response({
            'teams': serializer.data,
            'pagination': {
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'has_more': offset + page_size < total_count
            },
            'summary': {
                'total_teams': total_count,
                'formed_teams': total_formed,
                'forming_teams': total_forming
            },
            'user_context': self._get_user_context(request.user)
        })
    
    def _get_user_context(self, user):
        """Get user context for determining available actions"""
        if not user.is_authenticated:
            return {'is_authenticated': False}
        
        user_membership = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).select_related('team').first()
        
        return {
            'is_authenticated': True,
            'has_team': bool(user_membership),
            'team_id': user_membership.team.id if user_membership else None,
            'user_province': self._get_user_province(user),
            'can_join_teams': not bool(user_membership)
        }
    
    @action(methods=['GET'], detail=False, url_path='formed')
    def get_formed_teams(self, request):
        """Get only formed teams"""
        # Temporarily set formation_status for filtering
        request.GET = request.GET.copy()
        request.GET['formation_status'] = 'formed'
        return self.list(request)
    
    @action(methods=['GET'], detail=False, url_path='forming')
    def get_forming_teams(self, request):
        """Get only teams in formation"""
        request.GET = request.GET.copy()
        request.GET['formation_status'] = 'forming'
        return self.list(request)
    
    @action(methods=['GET'], detail=False, url_path='filters')
    def get_available_filters(self, request):
        """Get available filter options"""
        # Get provinces with teams
        provinces_with_teams = Province.objects.filter(
            team_formation_resumes__user__team_requests__user_role='C',
            team_formation_resumes__user__team_requests__status='A'
        ).distinct().values('id', 'title')
        
        # Get projects with teams
        projects_with_teams = models.Project.objects.filter(
            teams__isnull=False
        ).distinct().values('id', 'title')
        
        # Formation status options
        formation_statuses = [
            {'value': 'formed', 'label': 'تیم‌های تشکیل‌شده'},
            {'value': 'forming', 'label': 'تیم‌های در حال تشکیل'},
            {'value': 'all', 'label': 'همه تیم‌ها'}
        ]
        
        # Team building stages
        stages = [
            {'value': 1, 'label': 'مرحله ناپایدار اول'},
            {'value': 2, 'label': 'مرحله ناپایدار دوم'},
            {'value': 3, 'label': 'مرحله ناپایدار سوم'},
            {'value': 4, 'label': 'مرحله پایدار'}
        ]
        
        return Response({
            'provinces': list(provinces_with_teams),
            'projects': list(projects_with_teams),
            'formation_statuses': formation_statuses,
            'stages': stages
        })
    
    @action(methods=['GET'], detail=False, url_path='by-province')
    def get_teams_by_province(self, request):
        """Get team statistics by province"""
        province_stats = {}
        
        provinces = Province.objects.filter(
            team_formation_resumes__user__team_requests__user_role='C',
            team_formation_resumes__user__team_requests__status='A'
        ).distinct()
        
        for province in provinces:
            teams_in_province = self.get_queryset().filter(
                Exists(
                    models.TeamRequest.objects.filter(
                        team=OuterRef('pk'),
                        user_role='C',
                        status='A',
                        request_type='JOIN',
                        user__resume__team_formation_province=province
                    )
                )
            )
            
            province_stats[province.title] = {
                'province_id': province.id,
                'total_teams': teams_in_province.count(),
                'formed_teams': teams_in_province.filter(member_count__gte=2).count(),
                'forming_teams': teams_in_province.filter(
                    member_count__lt=F('count'),
                    member_count__gte=1
                ).count()
            }
        
        return Response(province_stats)
    
    @action(methods=['GET'], detail=True, url_path='join-options')
    def get_team_join_options(self, request, pk=None):
        """
        Get available join options for a specific team
        For free users: can request to join
        """
        try:
            team = self.get_object()
        except models.Team.DoesNotExist:
            return Response(
                {'error': 'تیم یافت نشد'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        user = request.user
        if not user.is_authenticated:
            return Response(
                {'error': 'برای مشاهده گزینه‌ها وارد سیستم شوید'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user already has a team
        user_has_team = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).exists()
        
        if user_has_team:
            return Response({
                'can_join': False,
                'reason': 'شما قبلاً عضو تیمی هستید',
                'available_actions': []
            })
        
        # Check team capacity
        current_members = team.get_member_count()
        stage_settings = team.get_stage_settings().filter(
            control_type='formation'
        ).first()
        max_size = stage_settings.max_team_size if stage_settings else team.count
        
        if current_members >= max_size:
            return Response({
                'can_join': False,
                'reason': 'تیم به حداکثر ظرفیت رسیده است',
                'available_actions': []
            })
        
        # Check if already has pending request
        existing_request = models.TeamRequest.objects.filter(
            team=team, user=user, status='W', request_type='JOIN'
        ).exists()
        
        if existing_request:
            return Response({
                'can_join': False,
                'reason': 'درخواست عضویت شما در انتظار بررسی است',
                'available_actions': [
                    {
                        'action': 'cancel_request',
                        'label': 'لغو درخواست عضویت'
                    }
                ]
            })
        
        # Check formation enabled
        if not team.is_formation_allowed():
            return Response({
                'can_join': False,
                'reason': 'امکان عضویت در این مرحله فعال نیست',
                'available_actions': []
            })
        
        # User can join
        serializer = TeamJoinOptionsSerializer({
            'team': team,
            'can_join': True,
            'current_members': current_members,
            'max_members': max_size,
            'available_spots': max_size - current_members
        }, context={'request': request})
        
        return Response(serializer.data)


class TeamPageView(APIView):
    permission_classes = [IsUser | IsSysgod]
    
    def get(self, request, team_id):
        try:
            team = models.Team.objects.select_related('project').get(id=team_id)
        except models.Team.DoesNotExist:
            return Response(
                {"message": "تیم یافت نشد!"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get team members
        members = models.TeamRequest.objects.filter(
            team=team, status='A', request_type='JOIN'
        ).select_related('user', 'user__resume', 'user__city')
        
        # Get pending requests
        pending_requests = models.TeamRequest.objects.filter(
            team=team, status='W'
        ).select_related('user', 'requested_by')
        
        # Build response
        team_data = team_serializers.TeamSerializer(
            team, context={'request': request}
        ).data
        
        # Add detailed members info
        team_data['detailed_members'] = []
        for member in members:
            user = member.user
            member_data = {
                'id': user.id,
                'full_name': user.full_name,
                'avatar': user.avatar.url if user.avatar else None,
                'role': member.get_user_role_display(),
                'is_leader': member.user_role == 'C',
                'joined_at': member.created_at,
                'province': None,
                'attractive_projects': []
            }
            
            # Add province info
            if user.resume and user.resume.team_formation_province:
                member_data['province'] = {
                    'id': user.resume.team_formation_province.id,
                    'title': user.resume.team_formation_province.title
                }
            elif user.city:
                member_data['province'] = {
                    'id': user.city.province.id,
                    'title': user.city.province.title
                }
            
            # Add attractive projects (top 3)
            attractions = models.ProjectAttractiveness.objects.filter(
                user=user
            ).select_related('project')[:3]
            
            member_data['attractive_projects'] = [
                {
                    'id': attr.project.id,
                    'title': attr.project.title
                }
                for attr in attractions
            ]
            
            team_data['detailed_members'].append(member_data)
        
        # Add pending requests info
        team_data['pending_requests'] = team_serializers.TeamRequestSerializer(
            pending_requests, many=True, context={'request': request}
        ).data
        
        return Response(team_data)