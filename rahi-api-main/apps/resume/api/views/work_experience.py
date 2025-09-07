from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from apps.api.permissions import ResumeStepPermission
from apps.resume import models
from apps.resume.api.serializers import work_experience as work_serializer
from apps.resume.services import ResumeModelViewSet
from apps.api.schema import TaggedAutoSchema


class ResumeWorkExperience(ResumeModelViewSet):
    schema = TaggedAutoSchema(tags=["Resume Work Experience"])
    serializer_class = work_serializer.WorkExperienceSerializer
    queryset = models.WorkExperience.objects.all()
    permission_classes = [IsAuthenticated, ResumeStepPermission]

    def get_queryset(self):
        query = super().get_queryset()
        return query.filter(resume=self._resume())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["resume"] = self._resume()
        return context

    def _resume(self):
        return get_object_or_404(models.Resume, pk=self.kwargs["resume_pk"], user=self.request.user)
