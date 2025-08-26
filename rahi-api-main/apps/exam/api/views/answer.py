from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.exam import models
from apps.exam.api.serializers import answer


class UserAnswerViewSet(ReadOnlyModelViewSet):
    serializer_class = answer.UserAnswer
    queryset = models.UserAnswer.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(user=self.request.user)
