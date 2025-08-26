from rest_framework.serializers import ModelSerializer

from apps.public.models import CompetitionRule


class CompetitionRuleSerializer(ModelSerializer):
    class Meta:
        model = CompetitionRule
        fields = "__all__"
