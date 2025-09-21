# apps/project/api/serializers/free_participants.py - Create new file

from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.account.models import Resume

User = get_user_model()


class FreeParticipantSerializer(serializers.ModelSerializer):
    latest_education = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    attractive_projects_count = serializers.SerializerMethodField()
    province_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'avatar_url', 'latest_education',
            'attractive_projects_count', 'province_name'
        ]
    
    def get_latest_education(self, obj):
        resume = getattr(obj, 'resume', None)
        if resume:
            latest_education = resume.educations.order_by('-graduation_year').first()
            if latest_education:
                return {
                    'degree_level': latest_education.degree_level,
                    'field_of_study': latest_education.field_of_study,
                    'university': latest_education.university
                }
        return None
    
    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
        return None
    
    def get_attractive_projects_count(self, obj):
        """Get count of user's attractive projects"""
        return obj.attractiveness_declarations.count()
    
    def get_province_name(self, obj):
        """Get user's province name for team formation"""
        resume = getattr(obj, 'resume', None)
        if resume and hasattr(resume, 'team_formation_province'):
            return resume.team_formation_province.title
        elif obj.city and hasattr(obj.city, 'province'):
            return obj.city.province.title
        return None


class FreeParticipantDetailSerializer(FreeParticipantSerializer):
    attractive_projects = serializers.SerializerMethodField()
    shared_attractive_projects = serializers.SerializerMethodField()
    belbin_role_tags = serializers.SerializerMethodField()
    contact_info = serializers.SerializerMethodField()
    education_history = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = FreeParticipantSerializer.Meta.fields + [
            'attractive_projects', 'shared_attractive_projects', 
            'belbin_role_tags', 'contact_info', 'education_history'
        ]
    
    def get_attractive_projects(self, obj):
        """Get user's attractive projects"""
        projects = obj.attractiveness_declarations.select_related(
            'project'
        ).order_by('project__title')[:10]  # Limit for performance
        
        return [
            {
                'id': decl.project.id,
                'title': decl.project.title,
                'short_description': decl.project.description[:100] + '...' if len(decl.project.description) > 100 else decl.project.description
            }
            for decl in projects
        ]
    
    def get_shared_attractive_projects(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []
        
        current_user = request.user
        
        # Get shared attractive projects
        current_user_projects = set(
            current_user.attractiveness_declarations.values_list(
                'project_id', flat=True
            )
        )
        
        participant_projects = obj.attractiveness_declarations.select_related(
            'project'
        ).filter(project_id__in=current_user_projects)
        
        return [
            {
                'id': decl.project.id,
                'title': decl.project.title
            }
            for decl in participant_projects
        ]
    
    def get_belbin_role_tags(self, obj):
        # This would need to be implemented based on your psychological test results
        # For now, return empty list or mock data
        resume = getattr(obj, 'resume', None)
        if resume:
            # You could add a belbin_roles field to Resume model
            # or extract from psychological test results
            return []  # Placeholder
        return []
    
    def get_contact_info(self, obj):
        request = self.context.get('request')
        current_user = request.user if request else None
        
        if not current_user or not current_user.is_authenticated:
            return {'contact_available': False}
        
        # Check if contact has been approved between users
        # This would need ContactRequest model implementation
        return {
            'contact_available': False,  # Default - must request contact
            'can_request_contact': current_user.id != obj.id,
        }
    
    def get_education_history(self, obj):
        """Get complete education history"""
        resume = getattr(obj, 'resume', None)
        if resume:
            educations = resume.educations.order_by('-graduation_year')
            return [
                {
                    'degree_level': edu.degree_level,
                    'field_of_study': edu.field_of_study,
                    'university': edu.university,
                    'graduation_year': edu.graduation_year
                }
                for edu in educations
            ]
        return []


class FreeParticipantActionSerializer(serializers.Serializer):
    """Serializer for available actions on free participants"""
    action = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    blocked = serializers.BooleanField(default=False)
    team_info = serializers.DictField(required=False)


class TeamProposalSerializer(serializers.Serializer):
    """Serializer for team proposal requests"""
    participant_id = serializers.IntegerField()
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_participant_id(self, value):
        """Validate that participant exists and is free"""
        try:
            user = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("کاربر یافت نشد")
        
        # Check if user is free (doesn't have active team membership)
        has_team = user.team_requests.filter(
            status='A', request_type='JOIN'
        ).exists()
        
        if has_team:
            raise serializers.ValidationError("این کاربر قبلاً عضو تیمی است")
        
        return value