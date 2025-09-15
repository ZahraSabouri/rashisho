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


class TeamDiscoveryViewSet(ModelViewSet):
    serializer_class = team_serializers.TeamSerializer
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        queryset = models.Team.objects.filter(
            # Exclude dissolved teams
            is_dissolution_in_progress=False
        ).select_related('project').annotate(
            member_count=Count(
                'requests',
                filter=Q(requests__status='A', requests__request_type='JOIN')
            )
        )
        
        # Filter by formation status
        formation_status = self.request.query_params.get('formation_status')
        if formation_status == 'formed':
            # Teams with enough members (at least 2 members)
            queryset = queryset.filter(member_count__gte=2)
        elif formation_status == 'forming':
            # Teams still looking for members
            queryset = queryset.filter(member_count__lt=models.F('count'))
        
        # Filter by province
        province_id = self.request.query_params.get('province')
        if province_id:
            # Filter teams based on leader's team formation province
            queryset = queryset.filter(
                Exists(
                    models.TeamRequest.objects.filter(
                        team=OuterRef('pk'),
                        user_role='C',
                        status='A',
                        request_type='JOIN',
                        user__resume__team_formation_province__id=province_id
                    )
                )
            )
        elif not province_id and hasattr(self.request, 'user') and self.request.user.is_authenticated:
            # Default to user's province if no filter specified
            user = self.request.user
            user_province = None
            
            # Try to get user's team formation province from resume
            if hasattr(user, 'resume') and user.resume:
                user_province = user.resume.team_formation_province_id
            
            # Fallback to user's city province
            if not user_province and user.city:
                user_province = user.city.province_id
            
            if user_province:
                queryset = queryset.filter(
                    Exists(
                        models.TeamRequest.objects.filter(
                            team=OuterRef('pk'),
                            user_role='C',
                            status='A',
                            request_type='JOIN',
                            user__resume__team_formation_province__id=user_province
                        )
                    )
                )
        
        # Filter by project if specified
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        return queryset.order_by('-created_at')
    
    def list(self, request):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        
        # Add summary metadata
        total_formed = queryset.filter(member_count__gte=2).count()
        total_forming = queryset.filter(member_count__lt=models.F('count')).count()
        
        return Response({
            'teams': serializer.data,
            'summary': {
                'total_teams': queryset.count(),
                'formed_teams': total_formed,
                'forming_teams': total_forming
            }
        })

    @action(methods=['GET'], detail=False, url_path='formed')
    def get_formed_teams(self, request):
        request.GET = request.GET.copy()
        request.GET['formation_status'] = 'formed'
        return self.list(request)

    @action(methods=['GET'], detail=False, url_path='forming')
    def get_forming_teams(self, request):
        request.GET = request.GET.copy()
        request.GET['formation_status'] = 'forming'
        return self.list(request)

    @action(methods=['GET'], detail=False, url_path='filters')
    def get_available_filters(self, request):
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
            {'value': 'forming', 'label': 'تیم‌های در حال تشکیل'}
        ]
        
        return Response({
            'provinces': list(provinces_with_teams),
            'projects': list(projects_with_teams),
            'formation_statuses': formation_statuses
        })

    @action(methods=['GET'], detail=False, url_path='by-province')
    def get_teams_by_province(self, request):
        # Get teams count by province
        province_stats = {}
        
        provinces = Province.objects.filter(is_active=True)
        for province in provinces:
            teams_count = models.Team.objects.filter(
                Exists(
                    models.TeamRequest.objects.filter(
                        team=OuterRef('pk'),
                        user_role='C',
                        status='A',
                        request_type='JOIN',
                        user__resume__team_formation_province=province
                    )
                )
            ).count()
            
            if teams_count > 0:
                province_stats[province.title] = {
                    'province_id': province.id,
                    'province_name': province.title,
                    'teams_count': teams_count
                }
        
        return Response(province_stats)

    @action(methods=['GET'], detail=True, url_path='join-options')
    def get_team_join_options(self, request, pk=None):
        team = self.get_object()
        user = request.user
        
        # Check user's current team status
        user_membership = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).first()
        
        # Check if team has space
        current_members = models.TeamRequest.objects.filter(
            team=team, status='A', request_type='JOIN'
        ).count()
        
        team_has_space = current_members < team.count
        
        # Check for existing requests
        existing_join_request = models.TeamRequest.objects.filter(
            user=user, team=team, request_type='JOIN', status='W'
        ).first()
        
        existing_invitation = models.TeamRequest.objects.filter(
            user=user, team=team, request_type='INVITE', status='W'
        ).first()
        
        response_data = {
            'team_id': team.id,
            'team_title': team.title,
            'current_members': current_members,
            'max_members': team.count,
            'team_has_space': team_has_space,
            'user_has_team': bool(user_membership),
            'user_is_leader': user_membership.user_role == 'C' if user_membership else False,
            'existing_join_request': bool(existing_join_request),
            'existing_invitation': bool(existing_invitation),
            'available_actions': []
        }
        
        # Determine available actions
        if not user_membership and team_has_space:
            if not existing_join_request and not existing_invitation:
                response_data['available_actions'].append({
                    'action': 'request_join',
                    'label': 'درخواست عضویت',
                    'description': 'درخواست عضویت در این تیم'
                })
        
        if existing_join_request:
            response_data['available_actions'].append({
                'action': 'cancel_join_request',
                'label': 'لغو درخواست',
                'description': 'لغو درخواست عضویت در این تیم'
            })
        
        if existing_invitation:
            response_data['available_actions'].extend([
                {
                    'action': 'accept_invitation',
                    'label': 'قبول دعوت',
                    'description': 'قبول دعوت عضویت در این تیم'
                },
                {
                    'action': 'reject_invitation',
                    'label': 'رد دعوت',
                    'description': 'رد دعوت عضویت در این تیم'
                }
            ])
        
        return Response(response_data)


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