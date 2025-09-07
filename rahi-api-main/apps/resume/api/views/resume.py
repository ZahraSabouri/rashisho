from django.db.models import Q
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import ResumePermission
from apps.api.roles import Roles
from apps.community.models import Community
from apps.project.models import ProjectAllocation
from apps.resume import models
from apps.resume.api.serializers import certificate, connection, language, project
from apps.resume.api.serializers import resume as resume_serializer
from apps.resume.services import create_last_step, update_last_step
from apps.api.schema import TaggedAutoSchema

class StartResume(APIView):
    schema = TaggedAutoSchema(tags=["Resume"])
    permission_classes = [IsAuthenticated]

    def post(self, request: HttpRequest):
        CURRENT_STEP = 1
        resume, created = models.Resume.objects.get_or_create(user=request.user)
        if not created:
            return Response({"detail": "شما از قبل یک رزومه دارید"}, status.HTTP_400_BAD_REQUEST)
        resume.next_step(CURRENT_STEP)
        serialized_resume = resume_serializer.ResumeSerializer(resume, context={"request": request}).data
        return Response(serialized_resume, status=status.HTTP_201_CREATED)


class MyResume(RetrieveAPIView):
    schema = TaggedAutoSchema(tags=["Resume"])
    permission_classes = [IsAuthenticated]
    serializer_class = resume_serializer.ResumeSerializer

    def get_object(self):
        return get_object_or_404(models.Resume, user=self.request.user)


class ResumeViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Resume"])
    serializer_class = resume_serializer.ResumeSerializer
    queryset = models.Resume.objects.all()
    permission_classes = [ResumePermission]

    def get_queryset(self):
        if self.request.user and self.request.user.has_role([Roles.sys_god]):
            return super().get_queryset()

        try:
            user_project = ProjectAllocation.objects.filter(user=self.request.user).first().project
            user_community = Community.objects.filter(manager=self.request.user).first()
            if not user_community:
                return (
                    super()
                    .get_queryset()
                    .filter(
                        Q(user=self.request.user)
                        | Q(user__in=[item.user for item in ProjectAllocation.objects.filter(project=user_project)])
                    )
                )

            if self.request.user.created_communities:
                return (
                    super()
                    .get_queryset()
                    .filter(
                        Q(user__community=self.request.user.created_communities)
                        | Q(user=self.request.user)
                        | Q(user__in=[item.user for item in ProjectAllocation.objects.filter(project=user_project)])
                    )
                )
        except Exception:
            pass

        return models.Resume.objects.filter(user=self.request.user)

    @action(methods=["post"], detail=True)
    def create_last_step(self, request, *args, **kwargs):
        """Here we register the last step of resume at once"""

        _resume = get_object_or_404(models.Resume, pk=self.kwargs["pk"], user=self.request.user)
        languages = self.request.data.get("languages", None)
        connections = self.request.data.get("connections", None)
        certificates = self.request.data.get("certificates", None)
        projects = self.request.data.get("projects", None)

        errors = []
        validated_options = []

        # Languages
        # if not languages:
        #     return Response({"message": "زبان ها نمی تواند خالی باشد!"})

        language_errors, language_validated_options = create_last_step(
            "languages", language.LanguageSerializer, languages, _resume
        )
        if language_errors:
            errors.append(language_errors)
        if language_validated_options:
            for item in language_validated_options:
                validated_options.append(item)

        # Connections
        # if not connections:
        #     return Response({"message": "راههای ارتباطی نمی تواند خالی باشد!"})

        connection_errors, connection_validated_options = create_last_step(
            "connections", connection.ConnectionSerializer, connections, _resume
        )
        if connection_validated_options:
            for item in connection_validated_options:
                validated_options.append(item)
        if connection_errors:
            errors.append(connection_errors)

        # Certificates
        if certificates:
            certificate_errors, certificate_validated_options = create_last_step(
                "certificates", certificate.CertificateSerializer, certificates, _resume
            )
            if certificate_validated_options:
                for item in certificate_validated_options:
                    validated_options.append(item)
            if certificate_errors:
                errors.append(certificate_errors)

        # Projects
        if projects:
            project_errors, project_validated_options = create_last_step(
                "projects", project.ProjectSerializer, projects, _resume
            )
            if project_validated_options:
                for item in project_validated_options:
                    validated_options.append(item)
            if project_errors:
                errors.append(project_errors)

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        for item in validated_options:
            item.save()

        return Response({"message": "عملیات با موفقیت انجام شد."}, status=status.HTTP_200_OK)

    @action(methods=["post"], detail=True)
    def update_last_step(self, request, *args, **kwargs):
        """Here we update the last step of project at once"""

        _resume = get_object_or_404(models.Resume, pk=self.kwargs["pk"], user=self.request.user)
        languages = self.request.data.get("languages", None)
        connections = self.request.data.get("connections", None)
        certificates = self.request.data.get("certificates", None)
        projects = self.request.data.get("projects", None)

        errors = []
        validated_options = []

        # Languages
        if languages:
            language_errors, language_validated_options = update_last_step(
                "language", language.LanguageSerializer, languages, _resume
            )
            if language_errors:
                errors.append(language_errors)
            if language_validated_options:
                for item in language_validated_options:
                    validated_options.append(item)

        # Connections
        if connections:
            connection_errors, connection_validated_options = update_last_step(
                "connection", connection.ConnectionSerializer, connections, _resume
            )
            if connection_validated_options:
                for item in connection_validated_options:
                    validated_options.append(item)
            if connection_errors:
                errors.append(connection_errors)

        # Certificates
        if certificates:
            certificate_errors, certificate_validated_options = update_last_step(
                "certificate", certificate.CertificateSerializer, certificates, _resume
            )
            if certificate_validated_options:
                for item in certificate_validated_options:
                    validated_options.append(item)
            if certificate_errors:
                errors.append(certificate_errors)

        # Projects
        if projects:
            project_errors, project_validated_options = update_last_step(
                "project", project.ProjectSerializer, projects, _resume
            )
            if project_validated_options:
                for item in project_validated_options:
                    validated_options.append(item)
            if project_errors:
                errors.append(project_errors)

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        models.Language.objects.filter(resume=_resume).delete()
        models.Certificate.objects.filter(resume=_resume).delete()
        models.Connection.objects.filter(resume=_resume).delete()
        models.Project.objects.filter(resume=_resume).delete()

        for item in validated_options:
            item.save()

        return Response({"message": "عملیات با موفقیت انجام شد."}, status=status.HTTP_200_OK)


class ResumeSecondToThirdStep(APIView):
    schema = TaggedAutoSchema(tags=["Resume"])
    def patch(self, request, *args, **kwargs):
        resume = get_object_or_404(models.Resume, user=self.request.user)
        if resume.steps["3"] == "started":
            resume.steps["3"] = "finished"
            if not resume.steps.get("4"):
                resume.steps["4"] = "started"
            resume.save()
        return Response()
