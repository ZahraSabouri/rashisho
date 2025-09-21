from rest_framework import serializers
from apps.project.models import TeamBuildingAnnouncement, TeamBuildingVideoButton


class TeamBuildingVideoButtonSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = TeamBuildingVideoButton
        fields = ['id', 'title', 'video_url', 'order']


class TeamBuildingAnnouncementSerializer(serializers.ModelSerializer):
    
    video_buttons = TeamBuildingVideoButtonSerializer(many=True, read_only=True)
    
    class Meta:
        model = TeamBuildingAnnouncement
        fields = ['id', 'title', 'content', 'video_buttons', 'order']
