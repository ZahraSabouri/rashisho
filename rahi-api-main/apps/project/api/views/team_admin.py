import io
import json
import xlsxwriter
import pandas as pd
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from rest_framework import status, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser

from apps.api.permissions import IsSysgod
from apps.project.models import Team, TeamRequest, Project
from apps.account.models import User
from apps.settings.models import Province
from apps.project.api.serializers.team import TeamSerializer


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
    """
    Excel import functionality to auto-create teams
    """
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
    """
    Advanced team management for admin users
    """
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
        """Add member to team by admin"""
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
        """Remove member from team by admin"""
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
        """Change team leader by admin"""
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
        """Get team statistics for admin dashboard"""
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