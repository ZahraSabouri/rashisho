from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.exam.models import UserAnswer
from apps.project.models import ProjectAttractiveness
from django.db import models
from rest_framework.response import Response

User = get_user_model()


class FreeParticipantSerializer(serializers.ModelSerializer):
    
    attractive_projects = serializers.SerializerMethodField()
    attractive_projects_mode = serializers.SerializerMethodField()
    belbin_role_tags = serializers.SerializerMethodField()
    latest_education = serializers.SerializerMethodField()
    team_formation_province = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'avatar', 'city',
            'attractive_projects', 'attractive_projects_mode',
            'belbin_role_tags', 'latest_education', 'team_formation_province'
        ]
        read_only_fields = ['id', 'full_name']

    def get_attractive_projects(self, obj):
        """Get user's attractive projects"""
        attractions = ProjectAttractiveness.objects.filter(
            user=obj
        ).select_related('project')[:5]  # Limit to 5 for performance
        
        return [
            {
                'id': attr.project.id,
                'title': attr.project.title,
                'is_shared': self._is_shared_with_current_user(attr.project)
            }
            for attr in attractions
        ]

    def get_attractive_projects_mode(self, obj):
        """
        Return the display mode for attractive projects
        Mode 1 (dropdown): 'dropdown'
        Mode 2 (expanded list): 'expanded'
        """
        # This could be a user preference, for now default to expanded
        # You can add a user preference field later
        return 'expanded'

    # def get_belbin_role_tags(self, obj):
    #     try:
    #         user_answer = UserAnswer.objects.get(user=obj)
    #         belbin_data = user_answer.belbin_answer
            
    #         if not belbin_data or belbin_data.get('status') != 'finished':
    #             return self._get_manual_role_tags(obj)
            
    #         # Extract top roles from Belbin results
    #         belbin_results = belbin_data.get('belbin', {})
    #         role_scores = []
            
    #         # Map Belbin roles to short tags
    #         BELBIN_ROLE_MAPPING = {
    #             'Plant': 'PL',
    #             'Resource Investigator': 'RI', 
    #             'Coordinator': 'CO',
    #             'Shaper': 'SH',
    #             'Monitor Evaluator': 'ME',
    #             'Teamworker': 'TW',
    #             'Implementer': 'IM',
    #             'Completer Finisher': 'CF',
    #             'Specialist': 'SP'
    #         }
            
    #         # Extract scores for each role
    #         for role, short_code in BELBIN_ROLE_MAPPING.items():
    #             score = belbin_results.get(role, 0)
    #             if isinstance(score, (int, float)) and score > 0:
    #                 role_scores.append((role, short_code, score))
            
    #         # Sort by score descending and take top 2-4 roles
    #         role_scores.sort(key=lambda x: x[2], reverse=True)
    #         top_roles = role_scores[:4]  # Max 4 roles
            
    #         if len(top_roles) >= 2:
    #             return [
    #                 {
    #                     'code': role[1], 
    #                     'name': role[0],
    #                     'score': role[2],
    #                     'source': 'auto'
    #                 }
    #                 for role in top_roles[:4]
    #             ]
    #         else:
    #             return self._get_manual_role_tags(obj)
                
    #     except UserAnswer.DoesNotExist:
    #         return self._get_manual_role_tags(obj)
    #     except Exception:
    #         return self._get_manual_role_tags(obj)

    def get_belbin_role_tags(self, obj):
        """Get role tags from Resume model"""
        if not hasattr(obj, 'resume') or not obj.resume:
            return []
            
        return obj.resume.get_role_tags(max_tags=4)
    def _get_manual_role_tags(self, obj):
        """
        Get manually set role tags if auto-generation fails
        This would typically come from a user profile field
        """
        # For now, return empty list - you can add a manual field later
        # to the User model or Resume model like 'manual_role_tags'
        return []

    def _is_shared_with_current_user(self, project):
        """Check if project is also attractive to current user"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
            
        return ProjectAttractiveness.objects.filter(
            user=request.user,
            project=project
        ).exists()

    def get_latest_education(self, obj):
        if not hasattr(obj, 'resume') or not obj.resume:
            return None
            
        latest_education = obj.resume.educations.order_by('-graduation_year').first()
        if not latest_education:
            return None
            
        return {
            'degree': latest_education.get_degree_display() if hasattr(latest_education, 'get_degree_display') else None,
            'field': latest_education.field.title if hasattr(latest_education, 'field') and latest_education.field else None,
            'university': latest_education.university.title if hasattr(latest_education, 'university') and latest_education.university else None,
        }

    def get_team_formation_province(self, obj):
        if not hasattr(obj, 'resume') or not obj.resume:
            return None
            
        if not obj.resume.team_formation_province:
            return None
            
        return {
            'id': obj.resume.team_formation_province.id,
            'title': obj.resume.team_formation_province.title
        }
    
    
    def list(self, request):
        queryset = self.get_queryset()
        current_user = request.user
        
        # Get current user's attractive projects for similarity scoring
        user_attractions = list(
            models.ProjectAttractiveness.objects.filter(
                user=current_user
            ).values_list('project_id', flat=True)
        )
        
        # Annotate users with shared project count for ordering
        users_data = []
        for user in queryset:
            user_attractions_ids = list(
                models.ProjectAttractiveness.objects.filter(
                    user=user
                ).values_list('project_id', flat=True)
            )
            
            # Calculate shared projects count
            shared_count = len(set(user_attractions) & set(user_attractions_ids))
            
            users_data.append({
                'user': user,
                'shared_projects_count': shared_count
            })
        
        # Sort by shared projects (desc), then alphabetically
        users_data.sort(key=lambda x: (-x['shared_projects_count'], x['user'].full_name))
        
        # Extract sorted users
        sorted_users = [item['user'] for item in users_data]
        
        # Paginate
        page = self.paginate_queryset(sorted_users)
        if page is not None:
            serializer = FreeParticipantSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = FreeParticipantSerializer(sorted_users, many=True, context={'request': request})
        return Response(serializer.data)


