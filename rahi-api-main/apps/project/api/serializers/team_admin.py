from rest_framework import serializers
from apps.project.models import TeamBuildingSettings, TeamBuildingStageDescription


class TeamBuildingSettingsSerializer(serializers.ModelSerializer):
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    control_type_display = serializers.CharField(source='get_control_type_display', read_only=True)
    
    class Meta:
        model = TeamBuildingSettings
        fields = [
            'id', 'stage', 'stage_display', 'control_type', 'control_type_display',
            'is_enabled', 'custom_description', 'min_team_size', 'max_team_size',
            'prevent_repeat_teammates', 'allow_auto_completion', 
            'formation_deadline_hours', 'created_at', 'updated_at'
        ]
    
    def validate(self, attrs):
        stage = attrs.get('stage')
        if stage not in [1, 2, 3, 4]:
            raise serializers.ValidationError(
                "مرحله باید بین 1 تا 4 باشد"
            )
        
        min_size = attrs.get('min_team_size', 2)
        max_size = attrs.get('max_team_size', 6)
        
        if min_size >= max_size:
            raise serializers.ValidationError(
                "حداقل اعضای تیم باید از حداکثر کمتر باشد"
            )
        
        if min_size < 2:
            raise serializers.ValidationError(
                "حداقل اعضای تیم نمی‌تواند کمتر از 2 باشد"
            )
        
        deadline = attrs.get('formation_deadline_hours', 24)
        if deadline < 1:
            raise serializers.ValidationError(
                "مهلت تشکیل تیم باید حداقل 1 ساعت باشد"
            )
        
        return attrs


class TeamBuildingStageDescriptionSerializer(serializers.ModelSerializer):
    page_type_display = serializers.CharField(source='get_page_type_display', read_only=True)
    
    class Meta:
        model = TeamBuildingStageDescription
        fields = [
            'id', 'page_type', 'page_type_display', 'title', 'description', 
            'is_active', 'created_at', 'updated_at'
        ]
    
    def validate_title(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError(
                "عنوان باید حداقل 5 کاراکتر باشد"
            )
        return value.strip()
    
    def validate_description(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "توضیحات باید حداقل 10 کاراکتر باشد"
            )
        return value.strip()


class TeamBuildingControlStatusSerializer(serializers.Serializer):
    stage = serializers.IntegerField()
    stage_name = serializers.CharField()
    formation_enabled = serializers.BooleanField()
    team_page_enabled = serializers.BooleanField()
    teams_count = serializers.IntegerField()
    active_teams_count = serializers.IntegerField()


class BulkControlUpdateSerializer(serializers.Serializer):
    controls = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=12
    )
    
    def validate_controls(self, value):
        valid_stages = [1, 2, 3, 4]
        valid_control_types = ['formation', 'team_page']
        
        for control in value:
            if 'stage' not in control or control['stage'] not in valid_stages:
                raise serializers.ValidationError(
                    "هر کنترل باید شامل مرحله معتبر (1-4) باشد"
                )
            
            if 'control_type' not in control or control['control_type'] not in valid_control_types:
                raise serializers.ValidationError(
                    "نوع کنترل باید formation یا team_page باشد"
                )
        
        return value
