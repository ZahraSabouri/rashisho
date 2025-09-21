from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.api.permissions import IsUser, IsSysgod
from apps.project.models import TeamBuildingAnnouncement
from apps.project.models import TeamBuildingAnnouncement, TeamBuildingSettings, TeamRequest, Team
from apps.project.api.serializers.team_announcements import TeamBuildingAnnouncementSerializer



class TeamBuildingAnnouncementsView(APIView):
    """Enhanced team building announcements with stage-specific content"""
    permission_classes = [IsUser | IsSysgod]
    
    def get(self, request):
        user = request.user
        
        # Get active announcements
        announcements = TeamBuildingAnnouncement.objects.filter(
            is_active=True
        ).prefetch_related('video_buttons').order_by('order', '-created_at')
        
        # Get user's team context
        user_context = self._get_user_context(user)
        
        # Get stage-specific descriptions
        stage_descriptions = self._get_stage_descriptions(user_context)
        
        serializer = TeamBuildingAnnouncementSerializer(announcements, many=True)
        
        return Response({
            'announcements': serializer.data,
            'user_context': user_context,
            'stage_descriptions': stage_descriptions,
            'controls_status': self._get_controls_status()
        }, status=status.HTTP_200_OK)
    
    def _get_user_context(self, user):
        """Get user's current team building context"""
        if not user.is_authenticated:
            return {'is_authenticated': False}
        
        user_membership = TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).select_related('team').first()
        
        context = {
            'is_authenticated': True,
            'has_team': bool(user_membership),
        }
        
        if user_membership:
            team = user_membership.team
            context.update({
                'team_id': team.id,
                'team_code': team.team_code,
                'team_title': team.title,
                'team_stage': team.team_building_stage,
                'team_stage_display': team.get_team_building_stage_display(),
                'user_role': user_membership.user_role,
                'user_role_display': user_membership.get_user_role_display(),
                'is_leader': user_membership.user_role == 'C',
                'member_count': team.get_member_count(),
                'max_members': team.count
            })
        
        return context
    
    def _get_stage_descriptions(self, user_context):
        """Get stage-specific descriptions"""
        from apps.project.models import TeamBuildingStageDescription
        
        descriptions = {}
        
        # Get all active descriptions
        all_descriptions = TeamBuildingStageDescription.objects.filter(
            is_active=True
        )
        
        for desc in all_descriptions:
            descriptions[desc.page_type] = {
                'title': desc.title,
                'description': desc.description
            }
        
        return descriptions
    
    def _get_controls_status(self):
        """Get current team building controls status"""
        controls = {}
        
        for stage in [1, 2, 3, 4]:
            controls[f'stage_{stage}'] = {
                'formation_enabled': TeamBuildingSettings.is_stage_formation_enabled(stage),
                'team_page_enabled': TeamBuildingSettings.is_stage_page_enabled(stage)
            }
        
        return controls


class TeamBuildingRulesView(APIView):
    """Enhanced team building rules with user-specific information"""
    permission_classes = [IsUser | IsSysgod]
    
    def get(self, request):
        user = request.user
        
        # Get basic team size rules
        basic_rules = self._get_basic_team_rules()
        
        # Get user-specific rules if authenticated
        user_specific_rules = {}
        if user.is_authenticated:
            user_specific_rules = self._get_user_specific_rules(user)
        
        # Get stage-specific rules
        stage_rules = self._get_stage_specific_rules()
        
        # Get current controls status
        controls_status = self._get_current_controls_status()
        
        return Response({
            'basic_rules': basic_rules,
            'user_specific_rules': user_specific_rules,
            'stage_rules': stage_rules,
            'controls_status': controls_status,
            'last_updated': self._get_last_rules_update()
        }, status=status.HTTP_200_OK)
    
    def _get_basic_team_rules(self):
        """Get basic team formation rules"""
        # Get default settings from stage 4 (stable)
        default_settings = TeamBuildingSettings.objects.filter(
            stage=4, control_type='formation'
        ).first()
        
        if default_settings:
            min_size = default_settings.min_team_size
            max_size = default_settings.max_team_size
        else:
            min_size = 2
            max_size = 6
        
        return {
            'team_size_limits': {
                'min_members': min_size,
                'max_members': max_size,
                'description': f'تیم‌ها باید حداقل {min_size} و حداکثر {max_size} عضو داشته باشند'
            },
            'invitation_rules': {
                'who_can_invite': 'فقط سرگروه و قائم مقام می‌توانند دعوت کنند',
                'capacity_rule': 'شما فقط به تعداد نفرات باقی‌مانده از حداکثر می‌توانید درخواست عضویت بفرستید',
                'example': 'اگر تیم شما ۳ عضو دارد و حداکثر ۵ است، فقط می‌توانید ۲ درخواست فعال داشته باشید'
            },
            'general_rules': [
                'هر شخص فقط می‌تواند عضو یک تیم باشد',
                'سرگروه می‌تواند تیم را منحل کند',
                'اعضا می‌توانند درخواست خروج از تیم دهند',
                'تغییر نقش اعضا فقط توسط سرگروه امکان‌پذیر است'
            ]
        }
    
    def _get_user_specific_rules(self, user):
        """Get rules specific to current user's situation"""
        user_membership = TeamRequest.objects.filter(
            user=user, status='A', request_type='JOIN'
        ).select_related('team').first()
        
        if not user_membership:
            return {
                'status': 'free_user',
                'available_actions': [
                    'ایجاد تیم جدید',
                    'درخواست عضویت در تیم‌های موجود',
                    'پیشنهاد تشکیل تیم با سایرین'
                ],
                'restrictions': []
            }
        
        team = user_membership.team
        current_members = team.get_member_count()
        
        # Get stage settings
        stage_settings = team.get_stage_settings().filter(control_type='formation').first()
        max_size = stage_settings.max_team_size if stage_settings else team.count
        remaining_spots = max_size - current_members
        
        # Get pending invites
        pending_invites = team.requests.filter(status='W', request_type='INVITE').count()
        max_invites = remaining_spots - pending_invites
        
        user_rules = {
            'status': 'team_member',
            'current_team': {
                'id': team.id,
                'title': team.title,
                'team_code': team.team_code,
                'current_members': current_members,
                'max_members': max_size,
                'remaining_spots': remaining_spots,
                'pending_invites': pending_invites,
                'user_role': user_membership.get_user_role_display(),
                'is_leader': user_membership.user_role == 'C'
            }
        }
        
        if user_membership.user_role in ['C', 'D']:  # Leader or Deputy
            user_rules['available_actions'] = [
                'دعوت اعضای جدید',
                'مدیریت درخواست‌های عضویت',
                'تغییر نقش اعضا'
            ]
            if user_membership.user_role == 'C':  # Leader only
                user_rules['available_actions'].extend([
                    'انحلال تیم',
                    'انتقال رهبری'
                ])
            
            user_rules['invitation_rules'] = {
                'max_active_invites': max(0, max_invites),
                'rule_description': f'شما فقط به تعداد {remaining_spots} نفر باقی‌مانده از حداکثر می‌توانید درخواست عضویت بفرستید'
            }
        else:  # Regular member
            user_rules['available_actions'] = [
                'درخواست خروج از تیم',
                'پیشنهاد تشکیل تیم جدید با سایرین'
            ]
        
        # Check repeat teammate rules
        stage_settings = team.get_stage_settings().filter(
            prevent_repeat_teammates=True
        ).first()
        
        if stage_settings:
            user_rules['repeat_teammate_rule'] = {
                'enabled': True,
                'description': 'قانون منع همتیمی کراری فعال است',
                'explanation': 'در صورت وجود شرکت‌کنندگان جدید، نمی‌توانید اعضای قبلی تیم‌های خود را دعوت کنید'
            }
        
        return user_rules
    
    def _get_stage_specific_rules(self):
        """Get rules for different team building stages"""
        stages_info = {}
        
        for stage in [1, 2, 3, 4]:
            stage_settings = TeamBuildingSettings.objects.filter(stage=stage)
            
            stage_info = {
                'stage_number': stage,
                'stage_name': dict(TeamBuildingSettings.STAGE_CHOICES)[stage],
                'is_unstable': stage in [1, 2, 3],
                'formation_enabled': TeamBuildingSettings.is_stage_formation_enabled(stage),
                'team_page_enabled': TeamBuildingSettings.is_stage_page_enabled(stage)
            }
            
            # Get specific settings
            formation_settings = stage_settings.filter(control_type='formation').first()
            if formation_settings:
                stage_info.update({
                    'min_team_size': formation_settings.min_team_size,
                    'max_team_size': formation_settings.max_team_size,
                    'repeat_prevention_enabled': formation_settings.prevent_repeat_teammates,
                    'auto_completion_allowed': formation_settings.allow_auto_completion,
                    'formation_deadline_hours': formation_settings.formation_deadline_hours
                })
            
            # Add stage-specific rules
            if stage in [1, 2, 3]:  # Unstable stages
                stage_info['special_rules'] = [
                    'تیم‌های ناپایدار برای مدت کوتاهی تشکیل می‌شوند',
                    'امکان تکمیل خودکار توسط سیستم وجود دارد',
                    'اعضا می‌توانند اعلام کنند آیا مایل به تکمیل تیم توسط سیستم هستند'
                ]
            else:  # Stable stage
                stage_info['special_rules'] = [
                    'تیم‌های پایدار برای کل دوره مسابقه باقی می‌مانند',
                    'تغییرات در تیم محدودتر است',
                    'امکان انتقال رهبری و قائم مقامی وجود دارد'
                ]
            
            stages_info[f'stage_{stage}'] = stage_info
        
        return stages_info
    
    def _get_current_controls_status(self):
        """Get current status of all team building controls"""
        return {
            'total_controls': 12,
            'enabled_controls': TeamBuildingSettings.objects.filter(is_enabled=True).count(),
            'active_stages': [
                stage for stage in [1, 2, 3, 4] 
                if TeamBuildingSettings.is_stage_formation_enabled(stage)
            ]
        }
    
    def _get_last_rules_update(self):
        """Get timestamp of last rules update"""
        latest_setting = TeamBuildingSettings.objects.order_by('-updated_at').first()
        return latest_setting.updated_at if latest_setting else None
