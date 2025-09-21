from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.public.api.serializers import competition_rule
from apps.public.models import CompetitionRule

from apps.api.schema import TaggedAutoSchema

class CompetitionRuleViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Completion Rule"])
    serializer_class = competition_rule.CompetitionRuleSerializer
    queryset = CompetitionRule.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]

    def get_object(self):
        return CompetitionRule.objects.first()
