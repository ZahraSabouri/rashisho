from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.public.api.serializers import common_questions
from apps.public.models import CommonQuestions

from apps.api.schema import TaggedAutoSchema

class CommonQuestionsViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Common Questions"])
    serializer_class = common_questions.CommonQuestionsSerializer
    queryset = CommonQuestions.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]

    def get_queryset(self):
        if not self.request.user.is_authenticated or self.request.user.is_authenticated and self.request.user.role == 1:
            self.pagination_class = None
        return super().get_queryset()
