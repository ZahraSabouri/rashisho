from django.shortcuts import get_object_or_404

from apps.api.permissions import IsUser, ResumeStepPermission
from apps.resume import models
from apps.resume.api.serializers import education
from apps.resume.services import ResumeModelViewSet
from apps.api.schema import TaggedAutoSchema

class ResumeEducationViewSet(ResumeModelViewSet):
    schema = TaggedAutoSchema(tags=["Resume Education"])
    serializer_class = education.EducationSerializer
    queryset = models.Education.objects.all().order_by("grade")
    permission_classes = [IsUser, ResumeStepPermission]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["resume"] = self._resume()
        return context

    def get_queryset(self):
        query = super().get_queryset()
        return query.filter(resume=self._resume())

    def _resume(self):
        return get_object_or_404(models.Resume, pk=self.kwargs["resume_pk"], user=self.request.user)
