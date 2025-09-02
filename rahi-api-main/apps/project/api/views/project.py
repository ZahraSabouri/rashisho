import io
import mimetypes
import os

import xlsxwriter
from django.db.models import Prefetch, ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from rest_framework import status, views
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet, mixins

from apps.account.models import User
from apps.api.permissions import IsAdminOrReadOnlyPermission, IsSysgod, IsUser, ReadOnly
from apps.project import models
from apps.project.api.filters import project
from apps.project.api.serializers import file_serializer
from apps.project.api.serializers import project as serializers
from apps.project.models import TeamRequest
from apps.project.services import allocate_project, generate_project_unique_code


class ProjectViewSet(ModelViewSet):
    serializer_class = serializers.ProjectSerializer
    queryset = models.Project.objects.all().prefetch_related(
        Prefetch("project_task", queryset=models.Task.objects.filter(is_active=True)), 
        "project_scenario",
        "tags",
        "study_fields"
    )

    permission_classes = [IsAdminOrReadOnlyPermission]
    filterset_class = project.ProjectFilterSet
    ordering_fields = "__all__"

    def get_queryset(self):
        """Filter queryset based on user role and project status"""
        qs = super().get_queryset()
        
        # For regular users, show all projects but mark inactive ones
        if hasattr(self.request.user, 'role'):
            if self.request.user.role == 1:  # Regular user
                # Show all visible projects, both active and inactive
                qs = qs.filter(visible=True)
            elif self.request.user.role == 2:  # Admin
                # Show all projects for admins
                pass
        else:
            # Anonymous users only see active, visible projects
            qs = qs.filter(visible=True, is_active=True)
            
        return qs

    def get_serializer_class(self):
        """Use appropriate serializer based on user role"""
        if isinstance(self.request.user, User):
            if self.request.user.role == 1:
                return serializers.UserProjectSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        """Enhanced project creation with proper validation"""
        study_fields = self.request.data.getlist("study_fields[]", [])

        if not study_fields:
            raise ValidationError("رشته های تحصیلی را وارد کنید!")

        # Projects are active by default
        serializer.save()
        
        # Clear related caches
        cache.delete_many([
            'active_projects_list',
            'project_status_stats',
            'homepage_projects'
        ])

    def perform_update(self, serializer):
        """Clear caches after project update"""
        serializer.save()
        
        # Clear related caches
        cache.delete_many([
            'active_projects_list', 
            'project_status_stats',
            'homepage_projects'
        ])

    # def perform_destroy(self, instance):
    #     try:
    #         models.Task.objects.filter(project=instance).delete()
    #         models.Scenario.objects.filter(project=instance).delete()
    #         super().perform_destroy(instance)

    #     except ProtectedError:
    #         raise ValidationError({"message": "قابلیت حذف وجود ندارد چون این پروژه در قسمت های دیگر استفاده شده است!"})

    def perform_destroy(self, instance):
        """Clear caches after project deletion"""
        super().perform_destroy(instance)
        
        # Clear related caches
        cache.delete_many([
            'active_projects_list',
            'project_status_stats', 
            'homepage_projects'
        ])    

    @action(methods=["get"], detail=False, serializer_class=serializers.ProjectListSerializer)
    def projects_list(self, request, *args, **kwargs):
        """For return just project id and title in project homepage"""

        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=["post"], detail=False, serializer_class=file_serializer.ImportFileSerializer)
    def project_allocate_excel(self, request, *args, **kwargs):
        """Get excel from admin and allocate projects to users."""
        import pandas as pd

        data = {"file": self.request.data.get("excel")}
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data.get("file")
        try:
            excel_content = pd.read_excel(file)
        except Exception as e:
            return Response(
                {"detail": f"خطایی در خواندن فایل اکسل رخ داده است!: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not excel_content.empty:
            return allocate_project(excel_content)
        else:
            return Response({"detail": "فایل اکسل خالی است!"}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["get"], detail=False, permission_classes=[IsSysgod])
    def sample_allocate_excel(self, request, *args, **kwargs):
        """Return the sample excel for project allocation for admin"""

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("نمونه اکسل تخصیص پروژه")
        worksheet.right_to_left()

        # Header Settings
        header_format = workbook.add_format(
            {
                "border": 1,
                "bold": True,
                "text_wrap": True,
                "valign": "vcenter",
                "align": "center",
                "bg_color": "#A5DEF2",
            }
        )
        # Columns width
        worksheet.set_column("A:A", 25)
        worksheet.set_column("B:B", 30)

        # Rows Height
        worksheet.set_row(0, 35)
        for row in range(1, 3000):
            worksheet.set_row(row, 25)

        # Generate headers
        worksheet.write("A1", "کد ملی", header_format)
        worksheet.write("B1", "کد پروژه", header_format)

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(Sample-project-allocation).xlsx"

        return response

    @action(["GET"], detail=False)
    def get_projects_stats(self, request, *args, **kwargs):
        projects = models.Project.objects.all()
        return Response(
            {
                "all_projects": projects.count(),
                "active_projects": projects.filter(is_visible=True).count(),
                # ''
            }
        )

    @action(detail=False, methods=['get'])
    def active_projects(self, request):
        """Get only active projects - cached endpoint"""
        cache_key = 'active_projects_list'
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            active_projects = self.get_queryset().filter(
                is_active=True, 
                visible=True
            )
            
            # Use pagination
            page = self.paginate_queryset(active_projects)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                cached_data = self.get_paginated_response(serializer.data).data
                cache.set(cache_key, cached_data, 1800)  # Cache for 30 minutes
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(active_projects, many=True)
            cached_data = serializer.data
            cache.set(cache_key, cached_data, 1800)
        
        return Response(cached_data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrReadOnlyPermission])
    def inactive_projects(self, request):
        """Get inactive projects - admin only"""
        inactive_projects = self.get_queryset().filter(is_active=False)
        
        page = self.paginate_queryset(inactive_projects)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(inactive_projects, many=True)
        return Response(serializer.data)

class ProjectPriorityViewSet(ModelViewSet):
    serializer_class = serializers.ProjectPrioritySerializer
    queryset = models.ProjectAllocation.objects.all()
    permission_classes = [IsUser | IsSysgod]
    filterset_class = project.ProjectPriorityFilterSet

    def get_queryset(self):
        queryset = super().get_queryset()
        if self._user().role == 1:
            return queryset.filter(user=self._user())
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def _user(self):
        return self.request.user


class FinalRepresentationViewSet(ModelViewSet):
    serializer_class = serializers.FinalRepresentationSerializer
    queryset = models.FinalRepresentation.objects.all()
    permission_classes = [IsUser | IsSysgod]
    filterset_fields = ["user", "project"]

    def get_serializer_context(self):
        res = super().get_serializer_context()
        res["allocated_project"] = self._project()
        return res

    def _user(self):
        return self.request.user

    def _project(self):
        user_allocation = models.ProjectAllocation.objects.filter(user=self._user()).first()
        if user_allocation:
            return user_allocation.project
        return None

    def perform_create(self, serializer):
        project_allocation: models.ProjectAllocation = self._project()

        if not project_allocation:
            raise ValidationError("به این کاربر پروژه اختصاص داده نشده است!")

        serializer.save(user=self._user(), project=self._project())

    @action(
        methods=["get"],
        detail=False,
        url_path="file/(?P<pk>[^/.]+)",
        permission_classes=[AllowAny],
        authentication_classes=(),
    )
    def final_rep_file(self, request, *args, **kwargs):
        import mimetypes
        import os

        from django.http import HttpResponse

        user_id = kwargs["pk"]
        final_rep = models.UserScenarioTaskFile.objects.filter(
            user_id=user_id, derivatives__derivatives_type="F"
        ).first()

        if final_rep and final_rep.file:
            file_path = final_rep.file.path
            if os.path.exists(file_path):
                name, extension = os.path.splitext(os.path.basename(file_path))
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = "application/octet-stream"

                with open(file_path, "rb") as pdf_file:
                    response = HttpResponse(pdf_file.read(), content_type=content_type)
                    response["Content-Disposition"] = f'attachment; filename="{name}{extension}"'
                    return response

        return Response({"message": "این کاربر فایل ارائه نهایی ندارد!"})


class FinalRepInfo(mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet):
    serializer_class = serializers.AdminFinalRepSerializer
    queryset = models.FinalRepresentation.objects.all()
    permission_classes = [IsSysgod]
    lookup_field = "user__id"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_field]}
        obj = get_object_or_404(queryset, **filter_kwargs)

        return obj


class FinalRepInfoV2(mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet):
    serializer_class = serializers.AdminFinalRepSerializerV2
    queryset = models.UserScenarioTaskFile.objects.filter(derivatives__derivatives_type="F")
    permission_classes = [IsSysgod]
    lookup_field = "user__id"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_field]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        return obj


class ProposalInfoVS(mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet):
    serializer_class = serializers.AdminFinalRepSerializerV2
    queryset = models.UserScenarioTaskFile.objects.filter(derivatives__derivatives_type="P")
    permission_classes = [IsSysgod]
    lookup_field = "user__id"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_field]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        return obj


class ScenarioVS(ModelViewSet):
    permission_classes = [IsAuthenticated, IsSysgod | ReadOnly]
    serializer_class = serializers.ScenarioSerializer
    queryset = models.Scenario.objects.all()

    @action(methods=["get"], detail=True, url_path="files")
    def scenario_files(self, request, pk, *args, **kwargs):
        import mimetypes
        import os

        from django.http import HttpResponse

        file_order = request.query_params.get("type", None)
        scenario = models.Scenario.objects.filter(id=pk).first()

        if scenario and file_order == "first" and scenario.first_file:
            file_path = scenario.first_file.path
            if os.path.exists(file_path):
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = "application/octet-stream"

                with open(file_path, "rb") as pdf_file:
                    response = HttpResponse(pdf_file.read(), content_type=content_type)
                    response["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
                    return response

        if scenario and scenario.second_file and file_order == "second":
            file_path = scenario.second_file.path
            if os.path.exists(file_path):
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = "application/octet-stream"

                with open(file_path, "rb") as pdf_file:
                    response = HttpResponse(pdf_file.read(), content_type=content_type)
                    response["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
                    return response

        return Response({"message": "فایل مورد نظر وجود ندارد!"}, status=status.HTTP_400_BAD_REQUEST)


class TaskVS(ModelViewSet):
    permission_classes = [IsAuthenticated, IsSysgod | ReadOnly]
    serializer_class = serializers.TaskSerializer
    queryset = models.Task.objects.all()

    @action(methods=["get"], detail=True, url_path="files")
    def task_files(self, request, pk, *args, **kwargs):
        import mimetypes
        import os

        from django.http import HttpResponse

        file_order = request.query_params.get("type", None)
        task = models.Task.objects.filter(id=pk).first()

        if task and file_order == "first" and task.first_file:
            file_path = task.first_file.path
            if os.path.exists(file_path):
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = "application/octet-stream"

                with open(file_path, "rb") as file:
                    response = HttpResponse(file.read(), content_type=content_type)
                    response["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
                    return response

        if task and task.second_file and file_order == "second":
            file_path = task.second_file.path
            if os.path.exists(file_path):
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = "application/octet-stream"

                with open(file_path, "rb") as pdf_file:
                    response = HttpResponse(pdf_file.read(), content_type=content_type)
                    response["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
                    return response

        return Response({"message": "فایل مورد نظر وجود ندارد!"}, status=status.HTTP_400_BAD_REQUEST)


class ProjectDerivativesVS(ModelViewSet):
    permission_classes = [IsAuthenticated, IsSysgod | ReadOnly]
    serializer_class = serializers.ProjectDerivativesSerializer
    queryset = models.ProjectDerivatives.objects.all()

    @action(methods=["get"], detail=False, url_path="final_reps")
    def get_final_reps(self, request, *args, **kwargs):
        project_id = request.query_params["project_id"]
        data = self.queryset.filter(project_id=project_id, derivatives_type="F").first()
        if data:
            serializer = self.serializer_class(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(data={"message": "یافت نشد!"}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["get"], detail=False, url_path="proposal")
    def get_proposal(self, request, *args, **kwargs):
        project_id = request.query_params["project_id"]
        data = self.queryset.filter(project_id=project_id, derivatives_type="P").first()
        if data:
            serializer = self.serializer_class(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(data={"message": "یافت نشد!"}, status=status.HTTP_400_BAD_REQUEST)


class HomePageProjectViewSet(mixins.ListModelMixin, GenericViewSet):
    """Updated homepage projects - only shows active projects"""
    serializer_class = serializers.HomePageProjectSerializer
    queryset = models.Project.objects.filter(visible=True, is_active=True)  # UPDATED
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        """Cached homepage project list"""
        cache_key = 'homepage_projects'
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            response = super().list(request, *args, **kwargs)
            cached_data = response.data
            cache.set(cache_key, cached_data, 3600)  # Cache for 1 hour
            return response
        
        return Response(cached_data)


class UserScenarioTaskFileAPV(views.APIView):
    permission_classes = [IsUser | IsSysgod]
    serializer_class = serializers.ScenarioTaskSerializer
    queryset = models.UserScenarioTaskFile.objects.all()

    def _user(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        queryset = models.UserScenarioTaskFile.objects.all()
        if self._user().role == 1:
            queryset = queryset.filter(user=self._user())
            if not queryset:
                user_team_request = models.TeamRequest.objects.filter(user=self._user(), status="A").last()
                if user_team_request:
                    user_team = user_team_request.team
                    team_head = models.TeamRequest.objects.filter(team=user_team, user_role="C").last().user
                    queryset = models.UserScenarioTaskFile.objects.filter(user=team_head)
                else:
                    return Response({"message": "شما عضو هیچ تیمی نیستید!"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(queryset, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        data = self.request.data
        scenario = data.get("scenario", None)
        task = data.get("task", None)
        final_rep = data.get("derivatives")

        user_file = None

        if scenario:
            user_file = models.UserScenarioTaskFile.objects.filter(user=self._user(), scenario_id=scenario).first()

        if task:
            user_file = models.UserScenarioTaskFile.objects.filter(user=self._user(), task_id=task).first()

        if final_rep:
            user_file = models.UserScenarioTaskFile.objects.filter(user=self._user(), derivatives_id=final_rep).first()

        serializer = self.serializer_class(data=data, context={"request": request})

        if user_file:
            serializer = self.serializer_class(
                instance=user_file, data=data, partial=True, context={"request": request}
            )

        serializer.is_valid(raise_exception=True)
        serializer.save(user=self._user())
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserTaskFileAV(views.APIView):
    permission_classes = [IsSysgod]

    def get(self, request, *args, **kwargs):
        """Here we return a file that team head upload it for task"""

        user_id = request.query_params.get("user_id", None)
        task_id = request.query_params.get("task_id", None)

        user_task_file = models.UserScenarioTaskFile.objects.filter(task_id=task_id, user_id=user_id).first()
        if user_task_file:
            file_path = user_task_file.file.path
            if os.path.exists(file_path):
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = "application/octet-stream"
                with open(file_path, "rb") as pdf_file:
                    response = HttpResponse(pdf_file.read(), content_type=content_type)
                    response["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
                    return response

        return Response({"message": "فایل مورد نظر وجود ندارد!"}, status=status.HTTP_400_BAD_REQUEST)


class IsTeamHeadAV(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = self.request.user
        team = TeamRequest.objects.filter(user=user, user_role="C").first()
        if team:
            return Response({"is_team_head": True}, status=status.HTTP_200_OK)

        return Response({"is_team_head": False}, status=status.HTTP_200_OK)


class ProjectTasksListAV(views.APIView):
    permission_classes = [IsSysgod]

    def get(self, request, *args, **kwargs):
        final_data = []
        projects = models.Project.objects.all().prefetch_related("project_scenario", "project_task")

        for p in projects:
            single_data = {}
            single_data["project_title"] = p.title
            single_data["tasks"] = p.project_task.values()
            if p.project_task.exists():
                final_data.append(single_data)

        return Response(final_data, status=status.HTTP_200_OK)
