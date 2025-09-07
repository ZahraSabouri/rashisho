import functools

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from apps.api.permissions import ResumeStepPermission
from apps.resume import models
from apps.resume.api.serializers import project
from apps.resume.services import ResumeModelViewSet
from apps.api.schema import TaggedAutoSchema

class ResumeProjectViewSet(ResumeModelViewSet):
    schema = TaggedAutoSchema(tags=["Resume Project"])
    serializer_class = project.ProjectSerializer
    queryset = models.Project.objects.all()
    permission_classes = [IsAuthenticated, ResumeStepPermission]

    @functools.cache
    def _resume(self):
        return get_object_or_404(models.Resume, pk=self.kwargs["resume_pk"], user=self.request.user)

    def get_queryset(self):
        query = super().get_queryset()
        return query.filter(resume=self._resume())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["resume"] = self._resume()
        return context
