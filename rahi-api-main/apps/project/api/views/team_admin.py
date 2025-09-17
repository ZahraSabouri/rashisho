import io
import json
import xlsxwriter
import pandas as pd
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q, F, Count, Prefetch
from django.utils import timezone
from rest_framework import status, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from django.db import models
from apps.common.models import BaseModel
from django.contrib.auth import get_user_model

from apps.api.permissions import IsSysgod, IsUser
from apps.project.models import Team, TeamRequest, Project
from apps.account.models import User
from apps.settings.models import Province
from apps.project.api.serializers.team import TeamSerializer
from apps.project.api.serializers.team_admin import TeamBuildingSettingsSerializer, TeamBuildingStageDescriptionSerializer
from apps.project.models import TeamBuildingSettings, TeamBuildingStageDescription


class EnhancedTeamReportView(APIView):
    permission_classes = [IsSysgod]
    
    def get(self, request):
        # Get filter parameters
        province_id = request.query_params.get('province')
        project_id = request.query_params.get('project') 
        team_status = request.query_params.get('team_status')  # 'formed', 'forming', 'all'
        team_building_stage = request.query_params.get('team_building_stage')
        search_query = request.query_params.get('search')
        
        # Build queryset with filters
        teams = Team.objects.select_related('project').prefetch_related(
            Prefetch(
                'requests', 
                queryset=TeamRequest.objects.filter(
                    status='A', 
                    request_type='JOIN'
                ).select_related('user', 'user__resume', 'user__city')
            )
        ).annotate(
            member_count=Count('requests', filter=Q(requests__status='A', requests__request_type='JOIN'))
        ).filter(member_count__gte=1)  # Only teams with at least 1 member
        
        # Apply filters
        if province_id:
            teams = teams.filter(
                requests__status='A',
                requests__user_role='C',  # Filter by team leader's province
                requests__user__resume__team_formation_province_id=province_id
            ).distinct()
        
        if project_id:
            teams = teams.filter(project_id=project_id)
        
        if team_status == 'formed':
            teams = teams.filter(member_count__gte=2)
        elif team_status == 'forming':
            teams = teams.filter(member_count__lt=2)
        
        if team_building_stage:
            teams = teams.filter(team_building_stage=team_building_stage)
        
        if search_query:
            teams = teams.filter(
                Q(title__icontains=search_query) |
                Q(team_code__icontains=search_query) |
                Q(requests__user__full_name__icontains=search_query) |
                Q(requests__user__user_info__national_id__icontains=search_query)
            ).distinct()
        
        teams = teams.order_by('team_building_stage', 'created_at')
        
        return self._generate_excel_report(teams, request.query_params)
    
    def _generate_excel_report(self, teams, filters):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("گزارش جامع تیم‌ها")
        worksheet.right_to_left()
        
        # Format definitions
        header_format = workbook.add_format({
            "border": 1, "bold": True, "text_wrap": True,
            "valign": "vcenter", "align": "center", "bg_color": "#4472C4",
            "font_color": "white", "font_size": 11
        })
        
        cell_format = workbook.add_format({
            "font_size": 10, "border": 1, "text_wrap": True,
            "valign": "vcenter", "align": "center"
        })
        
        leader_format = workbook.add_format({
            "font_size": 10, "border": 1, "text_wrap": True,
            "valign": "vcenter", "align": "center", "bg_color": "#E7F3FF"
        })
        
        # Set column widths
        widths = [20, 15, 15, 25, 12, 15, 10, 20, 15, 30, 15, 20]
        for i, width in enumerate(widths):
            worksheet.set_column(i, i, width)
        
        # Headers
        headers = [
            "نام تیم", "کد تیم", "مرحله تیم‌سازی", "نام پروژه", "تعداد اعضا", 
            "وضعیت تیم", "نقش عضو", "نام و نام خانوادگی", "کد ملی", 
            "شماره موبایل", "جنسیت", "استان تشکیل تیم"
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data rows
        row = 1
        for team in teams:
            team_members = team.requests.all()
            if not team_members:
                continue
                
            # Get team leader info
            leader = team_members.filter(user_role='C').first()
            leader_province = ""
            if leader and leader.user.resume and leader.user.resume.team_formation_province:
                leader_province = leader.user.resume.team_formation_province.title
            
            team_status = "تشکیل شده" if team.member_count >= 2 else "در حال تشکیل"
            
            for i, member in enumerate(team_members):
                user = member.user
                
                # Determine format based on role
                fmt = leader_format if member.user_role == 'C' else cell_format
                
                data = [
                    team.title if i == 0 else "",  # Only show team name on first row
                    team.team_code if i == 0 else "",
                    team.get_team_building_stage_display() if i == 0 else "",
                    team.project.title if i == 0 else "",
                    team.member_count if i == 0 else "",
                    team_status if i == 0 else "",
                    member.get_user_role_display(),
                    user.full_name,
                    user.user_info.get('national_id', ''),
                    user.user_info.get('mobile_number', ''),
                    user.get_gender_display() if hasattr(user, 'get_gender_display') else '',
                    leader_province if i == 0 else ""
                ]
                
                for col, value in enumerate(data):
                    worksheet.write(row, col, str(value) if value else "", fmt)
                
                row += 1
            
            # Add separator row between teams
            if row < 1000:  # Prevent excessive rows
                row += 1
        
        # Add summary sheet
        summary_sheet = workbook.add_worksheet("خلاصه آمار")
        summary_sheet.right_to_left()
        
        # Summary statistics
        total_teams = teams.count()
        formed_teams = teams.filter(member_count__gte=2).count()
        forming_teams = teams.filter(member_count__lt=2).count()
        
        stage_stats = {}
        for stage in Team.TEAM_STAGES:
            count = teams.filter(team_building_stage=stage[0]).count()
            stage_stats[stage[1]] = count
        
        # Write summary
        summary_sheet.write('A1', 'آمار کلی تیم‌ها', header_format)
        summary_sheet.write('A3', 'تعداد کل تیم‌ها:', cell_format)
        summary_sheet.write('B3', total_teams, cell_format)
        summary_sheet.write('A4', 'تیم‌های تشکیل شده:', cell_format)
        summary_sheet.write('B4', formed_teams, cell_format)
        summary_sheet.write('A5', 'تیم‌های در حال تشکیل:', cell_format)
        summary_sheet.write('B5', forming_teams, cell_format)
        
        summary_sheet.write('A7', 'آمار بر اساس مرحله:', header_format)
        row = 8
        for stage_name, count in stage_stats.items():
            summary_sheet.write(f'A{row}', stage_name, cell_format)
            summary_sheet.write(f'B{row}', count, cell_format)
            row += 1
        
        workbook.close()
        output.seek(0)
        
        # Generate filename with filters
        filename = "team-report"
        if filters.get('province'):
            province = Province.objects.filter(id=filters.get('province')).first()
            if province:
                filename += f"-{province.title}"
        
        if filters.get('team_status'):
            filename += f"-{filters.get('team_status')}"
        
        filename += ".xlsx"
        
        response = HttpResponse(
            output, 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class TeamBulkImportView(APIView):
    permission_classes = [IsSysgod]
    parser_classes = [MultiPartParser]
    
    def post(self, request):
        """
        Import teams from Excel file
        Expected Excel format:
        - Column A: Team Name
        - Column B: Project ID or Name  
        - Column C: Team Building Stage (1-4)
        - Column D: Leader National ID
        - Column E: Leader Name
        - Column F: Member 1 National ID
        - Column G: Member 1 Name
        - ... (up to 6 members total)
        """
        
        excel_file = request.FILES.get('file')
        if not excel_file:
            return Response(
                {"error": "فایل اکسل الزامی است"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file, sheet_name=0)
            
            results = {
                'total_rows': len(df),
                'successful_teams': 0,
                'failed_teams': 0,
                'errors': []
            }
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        self._process_team_row(row, index + 2, results)  # +2 for header and 0-index
                    except Exception as e:
                        results['failed_teams'] += 1
                        results['errors'].append({
                            'row': index + 2,
                            'error': str(e)
                        })
            
            return Response(results, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"خطا در پردازش فایل: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _process_team_row(self, row, row_number, results):
        """Process a single team row from Excel"""
        
        # Extract basic team info
        team_name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else None
        project_identifier = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else None
        team_stage = int(row.iloc[2]) if pd.notna(row.iloc[2]) else 4
        
        if not team_name or not project_identifier:
            raise ValueError(f"نام تیم و شناسه پروژه الزامی است")
        
        # Find or create project
        project = None
        try:
            # Try by ID first
            project = Project.objects.get(id=project_identifier)
        except (Project.DoesNotExist, ValueError):
            # Try by title
            project = Project.objects.filter(title__icontains=project_identifier).first()
            
        if not project:
            raise ValueError(f"پروژه با شناسه '{project_identifier}' یافت نشد")
        
        # Validate team stage
        if team_stage not in [1, 2, 3, 4]:
            raise ValueError(f"مرحله تیم‌سازی باید بین 1 تا 4 باشد")
        
        # Create team
        team = Team.objects.create(
            title=team_name,
            project=project,
            team_building_stage=team_stage,
            count=6  # Default max members
        )
        
        # Process team members (leader + up to 5 members)
        member_count = 0
        for i in range(3, min(len(row), 15), 2):  # National ID, Name pairs starting from column D
            national_id = str(row.iloc[i]).strip() if pd.notna(row.iloc[i]) else None
            member_name = str(row.iloc[i+1]).strip() if pd.notna(row.iloc[i+1]) else None
            
            if not national_id or national_id == 'nan':
                break
            
            # Find user by national ID
            user = User.objects.filter(
                user_info__national_id=national_id
            ).first()
            
            if not user:
                # Create user if not exists (basic info only)
                user = User.objects.create(
                    user_info={
                        'national_id': national_id,
                        'mobile_number': f'0900000{member_count:04d}'  # Temporary mobile
                    },
                    full_name=member_name or f"کاربر {national_id}"
                )
            
            # Check if user is already in a team
            existing_membership = TeamRequest.objects.filter(
                user=user, status='A', request_type='JOIN'
            ).first()
            
            if existing_membership:
                raise ValueError(f"کاربر {user.full_name} ({national_id}) قبلاً عضو تیم دیگری است")
            
            # Create team membership
            user_role = 'C' if member_count == 0 else 'M'  # First member is leader
            TeamRequest.objects.create(
                team=team,
                user=user,
                user_role=user_role,
                status='A',
                request_type='JOIN',
                requested_by=None  # Admin import
            )
            
            member_count += 1
            if member_count >= 6:  # Max 6 members
                break
        
        if member_count == 0:
            team.delete()
            raise ValueError("حداقل یک عضو (سرگروه) برای تیم الزامی است")
        
        results['successful_teams'] += 1


class TeamAdminManagementViewSet(viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    permission_classes = [IsSysgod]
    
    def get_queryset(self):
        queryset = Team.objects.select_related('project').prefetch_related(
            'requests__user'
        ).annotate(
            member_count=Count('requests', filter=Q(requests__status='A', requests__request_type='JOIN'))
        )
        
        # Advanced filtering
        province = self.request.query_params.get('province')
        project = self.request.query_params.get('project')
        team_status = self.request.query_params.get('team_status')
        search = self.request.query_params.get('search')
        
        if province:
            queryset = queryset.filter(
                requests__status='A',
                requests__user_role='C',
                requests__user__resume__team_formation_province_id=province
            ).distinct()
        
        if project:
            queryset = queryset.filter(project_id=project)
        
        if team_status == 'formed':
            queryset = queryset.filter(member_count__gte=2)
        elif team_status == 'forming':
            queryset = queryset.filter(member_count__lt=2)
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(team_code__icontains=search) |
                Q(requests__user__full_name__icontains=search) |
                Q(requests__user__user_info__national_id__icontains=search)
            ).distinct()
        
        return queryset.order_by('-created_at')
    
    @action(methods=['POST'], detail=True, url_path='add-member')
    def add_member(self, request, pk=None):
        team = self.get_object()
        national_id = request.data.get('national_id')
        user_role = request.data.get('user_role', 'M')
        
        if not national_id:
            return Response(
                {"error": "کد ملی الزامی است"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find user
        user = User.objects.filter(user_info__national_id=national_id).first()
        if not user:
            return Response(
                {"error": "کاربر با این کد ملی یافت نشد"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is already in a team
        existing = TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).first()
        
        if existing:
            return Response(
                {"error": f"کاربر قبلاً عضو تیم {existing.team.title} است"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add to team
        TeamRequest.objects.create(
            team=team,
            user=user,
            user_role=user_role,
            status='A',
            request_type='JOIN',
            requested_by=request.user
        )
        
        return Response({"message": "کاربر با موفقیت به تیم اضافه شد"})
    
    @action(methods=['POST'], detail=True, url_path='remove-member')
    def remove_member(self, request, pk=None):
        team = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {"error": "شناسه کاربر الزامی است"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        membership = TeamRequest.objects.filter(
            team=team, user_id=user_id, status='A', request_type='JOIN'
        ).first()
        
        if not membership:
            return Response(
                {"error": "کاربر در این تیم یافت نشد"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if removing leader
        if membership.user_role == 'C':
            other_members = team.requests.filter(
                status='A', request_type='JOIN'
            ).exclude(id=membership.id)
            
            if other_members.exists():
                return Response(
                    {"error": "برای حذف سرگروه، ابتدا یکی از اعضا را به عنوان سرگروه جدید تعین کنید"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        membership.delete()
        return Response({"message": "کاربر از تیم حذف شد"})
    
    @action(methods=['POST'], detail=True, url_path='change-leader')
    def change_leader(self, request, pk=None):
        team = self.get_object()
        new_leader_id = request.data.get('user_id')
        
        if not new_leader_id:
            return Response(
                {"error": "شناسه سرگروه جدید الزامی است"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find new leader membership
        new_leader = TeamRequest.objects.filter(
            team=team, user_id=new_leader_id, status='A', request_type='JOIN'
        ).first()
        
        if not new_leader:
            return Response(
                {"error": "کاربر در این تیم یافت نشد"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Demote current leader to member
            current_leader = team.requests.filter(
                status='A', request_type='JOIN', user_role='C'
            ).first()
            
            if current_leader:
                current_leader.user_role = 'M'
                current_leader.save()
            
            # Promote new leader
            new_leader.user_role = 'C'
            new_leader.save()
        
        return Response({"message": f"سرگروه تیم به {new_leader.user.full_name} تغییر یافت"})
    
    @action(methods=['GET'], detail=False, url_path='statistics')
    def get_statistics(self, request):
        teams = self.get_queryset()
        
        stats = {
            'total_teams': teams.count(),
            'formed_teams': teams.filter(member_count__gte=2).count(),
            'forming_teams': teams.filter(member_count__lt=2).count(),
            'stages': {},
            'provinces': {},
            'projects': {}
        }
        
        # Stage statistics
        for stage in Team.TEAM_STAGES:
            count = teams.filter(team_building_stage=stage[0]).count()
            stats['stages'][stage[1]] = count
        
        # Province statistics (top 10)
        province_stats = Province.objects.filter(
            team_formation_resumes__user__team_requests__status='A',
            team_formation_resumes__user__team_requests__user_role='C'
        ).annotate(
            team_count=Count('team_formation_resumes__user__team_requests__team', distinct=True)
        ).order_by('-team_count')[:10]
        
        for province in province_stats:
            stats['provinces'][province.title] = province.team_count
        
        # Project statistics (top 10)
        project_stats = Project.objects.annotate(
            team_count=Count('teams')
        ).order_by('-team_count')[:10]
        
        for project in project_stats:
            stats['projects'][project.title] = project.team_count
        
        return Response(stats)


class TeamBuildingSettingsViewSet(ModelViewSet):
    serializer_class = TeamBuildingSettingsSerializer
    queryset = TeamBuildingSettings.objects.all().order_by('stage', 'control_type')
    permission_classes = [IsSysgod]
    
    @action(methods=['GET'], detail=False, url_path='all-controls')
    def get_all_controls(self, request):
        """Get all 12 controls in organized format"""
        controls = {}
        
        for stage in [1, 2, 3, 4]:
            stage_name = f"stage_{stage}"
            controls[stage_name] = {
                'stage_number': stage,
                'stage_name': TeamBuildingSettings.STAGE_CHOICES[stage-1][1],
                'formation': self._get_or_create_control(stage, 'formation'),
                'team_page': self._get_or_create_control(stage, 'team_page')
            }
        
        return Response(controls, status=status.HTTP_200_OK)
    
    def _get_or_create_control(self, stage, control_type):
        setting, created = TeamBuildingSettings.objects.get_or_create(
            stage=stage,
            control_type=control_type,
            defaults={
                'is_enabled': False,
                'custom_description': '',
                'min_team_size': 2,
                'max_team_size': 6,
                'prevent_repeat_teammates': True,
                'allow_auto_completion': True,
                'formation_deadline_hours': 24
            }
        )
        return TeamBuildingSettingsSerializer(setting).data
    
    @action(methods=['POST'], detail=False, url_path='bulk-update')
    def bulk_update_controls(self, request):
        data = request.data.get('controls', [])
        
        updated_controls = []
        
        for control_data in data:
            setting = TeamBuildingSettings.objects.filter(
                stage=control_data.get('stage'),
                control_type=control_data.get('control_type')
            ).first()
            
            if setting:
                serializer = TeamBuildingSettingsSerializer(
                    setting, data=control_data, partial=True
                )
                if serializer.is_valid():
                    serializer.save()
                    updated_controls.append(serializer.data)
        
        return Response({
            'message': f'{len(updated_controls)} کنترل با موفقیت به‌روزرسانی شد',
            'updated_controls': updated_controls
        }, status=status.HTTP_200_OK)
    
    @action(methods=['GET'], detail=False, url_path='stage-status/(?P<stage>[1-4])')  
    def get_stage_status(self, request, stage=None):
        try:
            stage = int(stage)
            if stage not in [1, 2, 3, 4]:
                return Response(
                    {'error': 'مرحله باید بین 1 تا 4 باشد'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            settings = TeamBuildingSettings.objects.filter(stage=stage)
            
            stage_info = {
                'stage': stage,
                'stage_name': dict(TeamBuildingSettings.STAGE_CHOICES)[stage],
                'formation_enabled': TeamBuildingSettings.is_stage_formation_enabled(stage),
                'team_page_enabled': TeamBuildingSettings.is_stage_page_enabled(stage),
                'settings': TeamBuildingSettingsSerializer(settings, many=True).data,
                'teams_in_stage': Team.objects.filter(team_building_stage=stage).count(),
                'active_teams': Team.objects.filter(
                    team_building_stage=stage,
                    requests__status='A',
                    requests__request_type='JOIN'
                ).distinct().count()
            }
            
            return Response(stage_info, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response(
                {'error': 'مرحله باید عدد باشد'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class TeamBuildingStageDescriptionViewSet(ModelViewSet):
    serializer_class = TeamBuildingStageDescriptionSerializer
    queryset = TeamBuildingStageDescription.objects.all()
    permission_classes = [IsSysgod]
    
    @action(methods=['GET'], detail=False, url_path='all-descriptions')
    def get_all_descriptions(self, request):
        """Get all page descriptions"""
        descriptions = {}
        
        for page_type, page_name in TeamBuildingStageDescription.PAGE_CHOICES:
            desc = TeamBuildingStageDescription.objects.filter(
                page_type=page_type
            ).first()
            
            descriptions[page_type] = {
                'page_name': page_name,
                'data': TeamBuildingStageDescriptionSerializer(desc).data if desc else None
            }
        
        return Response(descriptions, status=status.HTTP_200_OK)


class TeamBuildingControlView(APIView):
    permission_classes = [IsUser | IsSysgod]
    
    def get(self, request):
        user = request.user
        
        # Get user's current team info
        user_membership = TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).select_related('team').first()
        
        current_stage = None
        user_team = None
        
        if user_membership:
            current_stage = user_membership.team.team_building_stage
            user_team = user_membership.team
        
        controls = {
            'stages': {
                '1': {
                    'formation_enabled': TeamBuildingSettings.is_stage_formation_enabled(1),
                    'team_page_enabled': TeamBuildingSettings.is_stage_page_enabled(1)
                },
                '2': {
                    'formation_enabled': TeamBuildingSettings.is_stage_formation_enabled(2),
                    'team_page_enabled': TeamBuildingSettings.is_stage_page_enabled(2)
                },
                '3': {
                    'formation_enabled': TeamBuildingSettings.is_stage_formation_enabled(3),
                    'team_page_enabled': TeamBuildingSettings.is_stage_page_enabled(3)
                },
                '4': {
                    'formation_enabled': TeamBuildingSettings.is_stage_formation_enabled(4),
                    'team_page_enabled': TeamBuildingSettings.is_stage_page_enabled(4)
                }
            },
            'user_context': {
                'has_team': bool(user_membership),
                'current_stage': current_stage,
                'team_id': user_team.id if user_team else None,
                'team_code': user_team.team_code if user_team else None,
                'can_access_formation': (
                    TeamBuildingSettings.is_stage_formation_enabled(current_stage) 
                    if current_stage else False
                ),
                'can_access_team_page': (
                    TeamBuildingSettings.is_stage_page_enabled(current_stage) 
                    if current_stage else False
                )
            }
        }
        
        return Response(controls, status=status.HTTP_200_OK)


# class UnstableTeamExportImportView(APIView):
class UnstableTeamExportImportView(GenericViewSet):
    permission_classes = [IsSysgod]
    parser_classes = [MultiPartParser]
    @action(methods=['POST'], detail=False, url_path='import-unstable-teams')
    def import_unstable_teams(self, request):
        result = {"created": 0, "updated": 0, "errors": []}
        return Response(result, status=status.HTTP_201_CREATED)
    
    @action(methods=['GET'], detail=False, url_path='export-unstable-teams')
    def export_unstable_teams(self, request):
        stage = request.query_params.get('stage')
        province_id = request.query_params.get('province')
        
        # Build queryset
        teams = Team.objects.filter(team_building_stage__in=[1, 2, 3])
        
        if stage:
            teams = teams.filter(team_building_stage=int(stage))
        
        # Get all team members with their info
        team_data = []
        
        for team in teams.select_related('project').prefetch_related(
            'requests__user',
            'requests__user__resume',
            'requests__user__city'
        ):
            members = team.requests.filter(status='A', request_type='JOIN').select_related('user')
            
            for member in members:
                user = member.user
                resume = getattr(user, 'resume', None)
                
                # Get province info
                province_name = ''
                if resume and hasattr(resume, 'team_formation_province'):
                    province_name = resume.team_formation_province.title if resume.team_formation_province else ''
                elif user.city:
                    province_name = user.city.title
                
                # Team status
                member_count = team.get_member_count()
                stage_settings = team.get_stage_settings().filter(control_type='formation').first()
                min_size = stage_settings.min_team_size if stage_settings else 2
                
                team_status = 'تیم کامل است' if member_count >= min_size else 'نیاز به تکمیل دارد'
                
                team_data.append({
                    'کد ملی': user.user_info.get('national_id', '') if user.user_info else '',
                    'آیدی یوزر': user.id,
                    'شماره موبایل': user.user_info.get('mobile_number', '') if user.user_info else '',
                    'نام و نام خانوادگی': user.full_name,
                    'استان': province_name,
                    'شناسه تیم': team.team_code,
                    'وضعیت تیم': team_status,
                    'مرحله': team.get_team_building_stage_display(),
                    'نقش در تیم': member.get_user_role_display(),
                    'تعداد اعضای فعلی': member_count,
                    'پروژه': team.project.title if team.project else '',
                    'تاریخ ایجاد تیم': team.created_at.strftime('%Y-%m-%d %H:%M')
                })
        
        # Apply province filter if specified
        if province_id:
            try:
                from apps.settings.models import Province
                province = Province.objects.get(id=province_id)
                team_data = [item for item in team_data if item['استان'] == province.title]
            except Province.DoesNotExist:
                pass
        
        # Create Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('تیم‌های ناپایدار')
        
        # Headers
        headers = [
            'کد ملی', 'آیدی یوزر', 'شماره موبایل', 'نام و نام خانوادگی',
            'استان', 'شناسه تیم', 'وضعیت تیم', 'مرحله', 'نقش در تیم',
            'تعداد اعضای فعلی', 'پروژه', 'تاریخ ایجاد تیم'
        ]
        
        # Header format
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4CAF50',
            'font_color': 'white',
            'align': 'center'
        })
        
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Write data
        for row, item in enumerate(team_data, 1):
            for col, header in enumerate(headers):
                worksheet.write(row, col, item.get(header, ''))
        
        # Auto-adjust column widths
        for col in range(len(headers)):
            worksheet.set_column(col, col, 15)
        
        workbook.close()
        output.seek(0)
        
        # Prepare response
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        filename = f'unstable_teams_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    def post(self, request):
        if 'file' not in request.FILES:
            return Response(
                {'error': 'فایل آپلود نشده است'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        stage = request.data.get('stage', 1)  # Default to unstable stage 1
        
        try:
            # Read Excel file
            import pandas as pd
            df = pd.read_excel(file)
            
            # Expected columns
            required_columns = [
                'کد ملی', 'آیدی یوزر', 'شماره موبایل', 'نام و نام خانوادگی',
                'استان', 'شناسه تیم', 'وضعیت تیم'
            ]
            
            # Validate columns
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return Response({
                    'error': f'ستون‌های مورد نیاز وجود ندارد: {", ".join(missing_columns)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            created_teams = []
            errors = []
            
            with transaction.atomic():
                # Group by team ID
                for team_code, group in df.groupby('شناسه تیم'):
                    if pd.isna(team_code):
                        continue
                    
                    try:
                        # Check if team already exists
                        existing_team = Team.objects.filter(team_code=team_code).first()
                        if existing_team:
                            errors.append(f'تیم با کد {team_code} قبلاً وجود دارد')
                            continue
                        
                        # Create team
                        team = Team.objects.create(
                            title=f'تیم {team_code}',
                            description=f'تیم ایجاد شده از فایل اکسل',
                            team_building_stage=int(stage),
                            count=len(group),
                            team_code=team_code
                        )
                        
                        # Add members
                        for _, row in group.iterrows():
                            try:
                                user_id = int(row['آیدی یوزر']) if not pd.isna(row['آیدی یوزر']) else None
                                national_id = str(row['کد ملی']) if not pd.isna(row['کد ملی']) else None
                                
                                user = None
                                if user_id:
                                    user = User.objects.filter(id=user_id).first()
                                elif national_id:
                                    user = User.objects.filter(
                                        user_info__national_id=national_id
                                    ).first()
                                
                                if not user:
                                    errors.append(
                                        f'کاربر با کد ملی {national_id} یا آیدی {user_id} پیدا نشد'
                                    )
                                    continue
                                
                                # Determine role (first member is leader)
                                role = 'C' if len(team.requests.all()) == 0 else 'M'
                                
                                TeamRequest.objects.create(
                                    team=team,
                                    user=user,
                                    user_role=role,
                                    status='A',
                                    request_type='JOIN'
                                )
                                
                            except Exception as e:
                                errors.append(f'خطا در اضافه کردن عضو {row["نام و نام خانوادگی"]}: {str(e)}')
                        
                        created_teams.append({
                            'team_code': team_code,
                            'member_count': team.get_member_count()
                        })
                        
                    except Exception as e:
                        errors.append(f'خطا در ایجاد تیم {team_code}: {str(e)}')
            
            return Response({
                'message': f'{len(created_teams)} تیم با موفقیت ایجاد شد',
                'created_teams': created_teams,
                'errors': errors,
                'total_processed': len(df.groupby('شناسه تیم'))
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'خطا در پردازش فایل: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(methods=['POST'], detail=False, url_path='auto-complete-unstable-teams')
    def auto_complete_unstable_teams(self, request):
        stage = request.data.get('stage')
        if not stage or stage not in [1, 2, 3]:
            return Response(
                {'error': 'مرحله باید یکی از مراحل ناپایدار (1، 2، 3) باشد'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get incomplete teams in this stage
        incomplete_teams = Team.objects.filter(
            team_building_stage=stage
        ).annotate(
            member_count=Count('requests', filter=Q(requests__status='A', requests__request_type='JOIN'))
        ).filter(
            member_count__lt=F('count')
        )
        
        # Get users without teams
        available_users = User.objects.exclude(
            team_requests__status='A',
            team_requests__request_type='JOIN'
        )
        
        completed_teams = []
        assigned_users = []
        
        with transaction.atomic():
            available_user_list = list(available_users)
            
            for team in incomplete_teams:
                needed_members = team.count - team.get_member_count()
                
                for _ in range(needed_members):
                    if not available_user_list:
                        break
                    
                    user = available_user_list.pop(0)
                    
                    TeamRequest.objects.create(
                        team=team,
                        user=user,
                        user_role='M',
                        status='A',
                        request_type='JOIN',
                        description='تکمیل خودکار توسط سیستم'
                    )
                    
                    assigned_users.append({
                        'user': user.full_name,
                        'team': team.team_code
                    })
                
                if team.get_member_count() >= team.count:
                    completed_teams.append(team.team_code)
        
        return Response({
            'message': f'{len(completed_teams)} تیم تکمیل شد',
            'completed_teams': completed_teams,
            'assigned_users_count': len(assigned_users),
            'remaining_available_users': len(available_user_list)
        }, status=status.HTTP_200_OK)




class EmergencyTeamManagementViewSet(ModelViewSet):
    serializer_class = TeamSerializer
    queryset = Team.objects.all()
    permission_classes = [IsSysgod]  # Only super admins
    
    @action(methods=['POST'], detail=True, url_path='emergency-dissolve')
    def emergency_dissolve_team(self, request, pk=None):
        team = self.get_object()
        reason = request.data.get('reason', 'حل اضطراری توسط ادمین')
        
        with transaction.atomic():
            # Get all active members
            active_members = models.TeamRequest.objects.filter(
                team=team, status='A', request_type='JOIN'
            )
            
            member_count = active_members.count()
            member_names = [req.user.full_name for req in active_members]
            
            # Remove all members immediately
            active_members.update(
                status='R',  # Rejected/Removed
                description=f'حذف اضطراری توسط ادمین: {reason}',
                updated_at=timezone.now()
            )
            
            # Cancel any pending requests
            models.TeamRequest.objects.filter(
                team=team, status='W'
            ).update(
                status='R',
                description=f'لغو اضطراری: {reason}',
                updated_at=timezone.now()
            )
            
            # Mark team as dissolved
            team.is_dissolution_in_progress = False  # Clear dissolution flag
            team.dissolution_requested_by = request.user
            team.dissolution_requested_at = timezone.now()
            team.save()
            
            # Log the emergency action
            self._log_emergency_action(
                team, request.user, 'EMERGENCY_DISSOLVE', reason, member_names
            )
        
        return Response({
            'message': 'تیم به صورت اضطراری منحل شد',
            'dissolved_team': {
                'team_code': team.team_code,
                'title': team.title,
                'removed_members': member_count,
                'member_names': member_names
            },
            'reason': reason,
            'dissolved_by': request.user.full_name,
            'dissolved_at': team.dissolution_requested_at
        }, status=status.HTTP_200_OK)
    
    @action(methods=['POST'], detail=True, url_path='force-remove-member')
    def force_remove_member(self, request, pk=None):
        team = self.get_object()
        user_id = request.data.get('user_id')
        reason = request.data.get('reason', 'حذف اضطراری توسط ادمین')
        
        if not user_id:
            return Response(
                {'error': 'user_id الزامی است'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            member_request = models.TeamRequest.objects.get(
                team=team, user_id=user_id, status='A', request_type='JOIN'
            )
        except models.TeamRequest.DoesNotExist:
            return Response(
                {'error': 'عضو مورد نظر یافت نشد'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if removing team leader
        if member_request.user_role == 'C':
            # Need to handle leadership transfer or team dissolution
            remaining_members = models.TeamRequest.objects.filter(
                team=team, status='A', request_type='JOIN'
            ).exclude(id=member_request.id)
            
            if remaining_members.exists():
                # Auto-promote deputy or first member to leader
                new_leader = remaining_members.filter(user_role='D').first()
                if not new_leader:
                    new_leader = remaining_members.first()
                
                new_leader.user_role = 'C'
                new_leader.save()
                
                leadership_info = {
                    'new_leader': new_leader.user.full_name,
                    'auto_promoted': True
                }
            else:
                # Team will be empty, mark for dissolution
                team.is_dissolution_in_progress = True
                team.dissolution_requested_by = request.user
                team.dissolution_requested_at = timezone.now()
                team.save()
                
                leadership_info = {
                    'team_dissolved': True,
                    'reason': 'حذف آخرین عضو'
                }
        else:
            leadership_info = None
        
        # Remove the member
        member_request.status = 'R'
        member_request.description = f'حذف اضطراری توسط ادمین: {reason}'
        member_request.save()
        
        # Log the action
        self._log_emergency_action(
            team, request.user, 'FORCE_REMOVE_MEMBER', reason, 
            [member_request.user.full_name]
        )
        
        response_data = {
            'message': 'عضو با موفقیت حذف شد',
            'removed_member': member_request.user.full_name,
            'reason': reason
        }
        
        if leadership_info:
            response_data['leadership_changes'] = leadership_info
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    @action(methods=['POST'], detail=True, url_path='force-add-member')
    def force_add_member(self, request, pk=None):
        team = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role', 'M')  # Default to member
        reason = request.data.get('reason', 'اضافه کردن اضطراری توسط ادمین')
        
        if not user_id:
            return Response(
                {'error': 'user_id الزامی است'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'کاربر یافت نشد'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user already in a team
        existing_membership = models.TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).first()
        
        if existing_membership:
            return Response({
                'error': 'کاربر قبلاً عضو تیمی است',
                'current_team': existing_membership.team.team_code
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Force add the member (ignoring all restrictions)
        with transaction.atomic():
            # If adding as leader, demote current leader
            if role == 'C':
                current_leader = models.TeamRequest.objects.filter(
                    team=team, user_role='C', status='A', request_type='JOIN'
                ).first()
                
                if current_leader:
                    current_leader.user_role = 'D'  # Demote to deputy
                    current_leader.save()
            
            # Create the membership
            models.TeamRequest.objects.create(
                team=team,
                user=user,
                user_role=role,
                status='A',
                request_type='JOIN',
                requested_by=request.user,
                description=f'اضافه کردن اضطراری توسط ادمین: {reason}'
            )
            
            # Log the action
            self._log_emergency_action(
                team, request.user, 'FORCE_ADD_MEMBER', reason, [user.full_name]
            )
        
        return Response({
            'message': 'عضو با موفقیت اضافه شد',
            'added_member': user.full_name,
            'role': models.TeamRequest.USER_ROLE[next(
                (i for i, (code, _) in enumerate(models.TeamRequest.USER_ROLE) if code == role), 
                0
            )][1],
            'reason': reason,
            'team_code': team.team_code
        }, status=status.HTTP_201_CREATED)
    
    @action(methods=['POST'], detail=True, url_path='bypass-approval-requirement')
    def bypass_approval_requirement(self, request, pk=None):
        """
        Temporarily disable approval requirement for team dissolution
        Mentioned in requirements: "admin can disable need for approval from others"
        """
        team = self.get_object()
        disable_duration_hours = int(request.data.get('duration_hours', 24))
        reason = request.data.get('reason', 'حالت اضطراری')
        
        # Create emergency bypass setting
        bypass_setting, created = models.EmergencyBypass.objects.get_or_create(
            team=team,
            bypass_type='DISSOLUTION_APPROVAL',
            defaults={
                'is_active': True,
                'created_by': request.user,
                'reason': reason,
                'expires_at': timezone.now() + timezone.timedelta(hours=disable_duration_hours)
            }
        )
        
        if not created:
            # Update existing bypass
            bypass_setting.is_active = True
            bypass_setting.reason = reason
            bypass_setting.expires_at = timezone.now() + timezone.timedelta(hours=disable_duration_hours)
            bypass_setting.save()
        
        return Response({
            'message': 'نیاز به تایید اعضا موقتاً غیرفعال شد',
            'bypass_active_until': bypass_setting.expires_at,
            'team_code': team.team_code,
            'reason': reason
        }, status=status.HTTP_200_OK)
    
    @action(methods=['GET'], detail=False, url_path='emergency-log')
    def get_emergency_log(self, request):
        """Get log of all emergency actions"""
        logs = models.EmergencyActionLog.objects.select_related(
            'team', 'admin_user'
        ).order_by('-created_at')[:100]  # Last 100 actions
        
        log_data = []
        for log in logs:
            log_data.append({
                'id': log.id,
                'team_code': log.team.team_code if log.team else 'N/A',
                'team_title': log.team.title if log.team else 'حذف شده',
                'action_type': log.action_type,
                'reason': log.reason,
                'affected_users': log.affected_users,
                'admin_user': log.admin_user.full_name,
                'created_at': log.created_at
            })
        
        return Response({
            'emergency_actions': log_data,
            'total_count': logs.count()
        })
    
    def _log_emergency_action(self, team, admin_user, action_type, reason, affected_users):
        """Log emergency action for audit trail"""
        models.EmergencyActionLog.objects.create(
            team=team,
            admin_user=admin_user,
            action_type=action_type,
            reason=reason,
            affected_users=affected_users
        )


# Additional models needed for emergency controls
class EmergencyBypass(BaseModel):
    """Model to track emergency bypasses"""
    
    BYPASS_TYPES = [
        ('DISSOLUTION_APPROVAL', 'عدم نیاز به تایید برای انحلال'),
        ('CAPACITY_LIMIT', 'عدم رعایت حد ظرفیت'),
        ('REPEAT_TEAMMATE_RULE', 'عدم رعایت قانون کراری')
    ]
    
    team = models.ForeignKey(
        'Team',
        on_delete=models.CASCADE,
        related_name='emergency_bypasses'
    )
    bypass_type = models.CharField(max_length=30, choices=BYPASS_TYPES)
    is_active = models.BooleanField(default=True)
    reason = models.TextField()
    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    
    class Meta(BaseModel.Meta):
        verbose_name = 'تنظیمات اضطراری'
        verbose_name_plural = 'تنظیمات اضطراری'


class EmergencyActionLog(BaseModel):
    """Log of emergency administrative actions"""
    
    ACTION_TYPES = [
        ('EMERGENCY_DISSOLVE', 'انحلال اضطراری'),
        ('FORCE_REMOVE_MEMBER', 'حذف اجباری عضو'),
        ('FORCE_ADD_MEMBER', 'اضافه کردن اجباری عضو'),
        ('BYPASS_APPROVAL', 'غیرفعال کردن تایید')
    ]
    
    team = models.ForeignKey(
        'Team',
        on_delete=models.SET_NULL,
        null=True,
        related_name='emergency_logs'
    )
    admin_user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='emergency_actions'
    )
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    reason = models.TextField()
    affected_users = models.JSONField(default=list)  # List of affected user names
    
    class Meta(BaseModel.Meta):
        verbose_name = 'لاگ اقدامات اضطراری'
        verbose_name_plural = 'لاگ اقدامات اضطراری'