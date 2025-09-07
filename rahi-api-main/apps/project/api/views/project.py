import io
import mimetypes
import os

import xlsxwriter
from django.db.models import Prefetch, ProtectedError, Count
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

from apps.api.pagination import Pagination
from apps.project.models import Project
from apps.project.api.serializers.project_list import ProjectAnnotatedListSerializer
from apps.project.api.filters.project import ProjectFilterSet 


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
    @action(detail=False, methods=["get"], url_path="annotated", permission_classes=[AllowAny])
    def annotated(self, request):
        """
        List projects with precomputed counts.

        Query params:
          - title: icontains filter (already supported by ProjectFilterSet)
          - study_fields: comma-separated ids (ProjectFilterSet)
          - ordering: e.g. '-allocations_count', '-tags_count', '-created_at'

        Returns paginated results using apps.api.pagination.Pagination.
        """
        # Base queryset (respect your current visibility rules if any)
        qs = (
        Project.objects.filter(visible=True, is_active=True)
        .prefetch_related("tags", "study_fields")
        .annotate(
            tags_count=Count("tags", distinct=True),
            allocations_count=Count("allocations", distinct=True),
            )
        )

        # Get applied filters info
        applied_filters = self._get_applied_filters(request.GET)
    
        # Apply ordering
        ordering = request.GET.get("ordering") or "-created_at"
        qs = qs.order_by(ordering)

        # Pagination consistent with your project style
        paginator = Pagination()
        page = paginator.paginate_queryset(qs, request)
        ser = ProjectAnnotatedListSerializer(page, many=True, context={"request": request})
    
        # Get filter and sorting metadata
        filter_metadata = self._get_filter_metadata(request)
        
        # Enhance paginated response with metadata
        response_data = paginator.get_paginated_response(ser.data).data
        response_data.update({
            'filters': filter_metadata,
            'applied_filters': applied_filters,
            'applied_filters_count': len(applied_filters),
            'sorting': {
                'current': ordering,
                'available_options': self._get_sorting_options()
            }
        })
        
        return Response(response_data)

    @action(methods=["get"], url_path="attractiveness", permission_classes=[AllowAny])
    def attractiveness(self, request, pk=None):
        from apps.project.services import can_show_attractiveness, count_project_attractiveness
        from apps.project.models import ProjectAttractiveness

        project = self.get_object()

        if not can_show_attractiveness(project):
            return Response({"project_id": str(project.id), "attractiveness": None, "user_selected": False})

        count = count_project_attractiveness(project.id)
        user_selected = False
        u = request.user
        if getattr(u, "is_authenticated", False):
            user_selected = ProjectAttractiveness.objects.filter(user=u, project=project).exists()

        return Response({
            "project_id": str(project.id),
            "attractiveness": count,
            "user_selected": user_selected
        })
    
    @action(methods=["post"], url_path="attractiveness/toggle", permission_classes=[IsAuthenticated])
    def toggle_attractiveness(self, request, pk=None):
        """
        Toggle user's 'attractiveness' (heart) on this project.
        - Allowed ONLY while the project can be selected (SELECTION_ACTIVE).
        - After selection is finished, we lock the count (no like/unlike).
        """
        from apps.project.models import ProjectAttractiveness
        from apps.project.services import can_select_projects, count_project_attractiveness

        project = self.get_object()

        # Freeze after selection phase
        if not can_select_projects(project): 
            return Response(
                {"detail": "Attractiveness is locked for this project."},
                status=status.HTTP_423_LOCKED
            )

        obj, created = ProjectAttractiveness.objects.get_or_create(user=request.user, project=project)
        if created:
            user_selected = True   # just hearted
        else:
            # toggle off (unheart)
            obj.delete()
            user_selected = False

        count = count_project_attractiveness(project.id)

        # keep keys the same to avoid frontend changes
        return Response({
            "project_id": str(project.id),
            "attractiveness": count,
            "user_selected": user_selected
        }, status=status.HTTP_200_OK)

    def _get_applied_filters(self, query_params):
        """Extract information about currently applied filters"""
        applied = []
        
        filter_mappings = {
            'title': 'عنوان',
            'search': 'جستجو کلی', 
            'company': 'شرکت',
            'study_fields': 'رشته‌های تحصیلی',
            'tags': 'کلیدواژه‌ها',
            'tag_category': 'دسته‌بندی تگ'
        }
        
        for param, label in filter_mappings.items():
            value = query_params.get(param)
            if value:
                applied.append({
                    'key': param,
                    'label': label,
                    'value': value,
                    'display_value': self._format_filter_display_value(param, value)
                })
        
        return applied

    def _format_filter_display_value(self, param, value):
        """Format filter values for display"""
        if param == 'study_fields':
            try:
                from apps.settings.models import StudyField
                field_ids = [int(id.strip()) for id in value.split(',') if id.strip().isdigit()]
                fields = StudyField.objects.filter(id__in=field_ids)
                return ', '.join([field.title for field in fields])
            except:
                return value
        
        elif param == 'tags':
            try:
                from apps.project.models import Tag
                # Handle both tag IDs and names
                tag_values = [v.strip() for v in value.split(',')]
                tag_ids = [v for v in tag_values if v.isdigit()]
                tag_names = [v for v in tag_values if not v.isdigit()]
                
                tags = Tag.objects.filter(
                    models.Q(id__in=tag_ids) | models.Q(name__in=tag_names)
                )
                return ', '.join([tag.name for tag in tags])
            except:
                return value
        
        elif param == 'tag_category':
            category_map = {
                'SKILL': 'مهارت',
                'TECH': 'فناوری', 
                'DOMAIN': 'حوزه',
                'KEYWORD': 'کلیدواژه'
            }
            return category_map.get(value, value)
        
        return value

    def _get_filter_metadata(self, request):
        """Get metadata about available filters and their options"""
        from apps.settings.models import StudyField
        from apps.project.models import Tag
        
        # Get available study fields (only those used in projects)
        available_study_fields = StudyField.objects.filter(
            project__visible=True,
            project__is_active=True
        ).distinct().values('id', 'title')
        
        # Get available tags by category
        available_tags = Tag.objects.filter(
            projects__visible=True,
            projects__is_active=True
        ).distinct().values('id', 'name', 'category')
        
        # Group tags by category
        tags_by_category = {}
        for tag in available_tags:
            category = tag['category']
            if category not in tags_by_category:
                tags_by_category[category] = []
            tags_by_category[category].append({
                'id': tag['id'],
                'name': tag['name']
            })
        
        # Get popular companies (for suggestions)
        from django.db.models import Count
        popular_companies = Project.objects.filter(
            visible=True, 
            is_active=True
        ).values('company').annotate(
            project_count=Count('id')
        ).order_by('-project_count')[:10]
        
        return {
            'study_fields': {
                'type': 'multiselect',
                'label': 'رشته‌های تحصیلی',
                'options': list(available_study_fields),
                'param': 'study_fields'
            },
            'tags': {
                'type': 'multiselect',
                'label': 'کلیدواژه‌ها',
                'options_by_category': tags_by_category,
                'param': 'tags'
            },
            'tag_category': {
                'type': 'select',
                'label': 'دسته‌بندی کلیدواژه',
                'options': [
                    {'value': 'SKILL', 'label': 'مهارت'},
                    {'value': 'TECH', 'label': 'فناوری'},
                    {'value': 'DOMAIN', 'label': 'حوزه'},
                    {'value': 'KEYWORD', 'label': 'کلیدواژه'}
                ],
                'param': 'tag_category'
            },
            'company': {
                'type': 'text',
                'label': 'شرکت',
                'suggestions': [c['company'] for c in popular_companies],
                'param': 'company'
            },
            'title': {
                'type': 'text',
                'label': 'عنوان پروژه',
                'param': 'title'
            },
            'search': {
                'type': 'text',
                'label': 'جستجو در همه فیلدها',
                'param': 'search',
                'description': 'جستجو در عنوان، توضیحات، شرکت، کلیدواژه‌ها و نام راهبر'
            }
        }

    def _get_sorting_options(self):
        """Get available sorting options"""
        return [
            {
                'value': '-created_at',
                'label': 'جدیدترین',
                'description': 'بر اساس تاریخ ایجاد (جدید به قدیم)'
            },
            {
                'value': 'created_at', 
                'label': 'قدیمی‌ترین',
                'description': 'بر اساس تاریخ ایجاد (قدیم به جدید)'
            },
            {
                'value': '-allocations_count',
                'label': 'محبوب‌ترین',
                'description': 'بر اساس تعداد انتخاب توسط کاربران'
            },
            {
                'value': '-tags_count',
                'label': 'بیشترین کلیدواژه',
                'description': 'بر اساس تعداد کلیدواژه‌ها'
            },
            {
                'value': 'title',
                'label': 'ترتیب الفبایی (الف-ی)',
                'description': 'بر اساس عنوان پروژه'
            },
            {
                'value': '-title',
                'label': 'ترتیب الفبایی (ی-الف)',
                'description': 'بر اساس عنوان پروژه (معکوس)'
            }
        ]

    def get_serializer_context(self):
        """
        Pass study field IDs into the serializer context so it can
        set the M2M after create/update.
        Works for both JSON and multipart.
        """
        ctx = super().get_serializer_context()
        data = self.request.data
        if hasattr(data, "getlist"):  # multipart/form-data
            ids = data.getlist("study_fields[]") or data.getlist("study_fields")
        else:                         # application/json
            ids = data.get("study_fields") or data.get("study_fields[]")

        # normalize to a list of ints/strings
        if ids is None:
            ids = []
        elif not isinstance(ids, (list, tuple)):
            ids = [ids]

        ctx["study_fields_ids"] = ids
        return ctx

    def perform_create(self, serializer):
        """
        Validate presence of study_fields in request (dev requirement),
        then save. Serializer should read `study_fields_ids` from context.
        """
        data = self.request.data
        if hasattr(data, "getlist"):
            ids = data.getlist("study_fields[]") or data.getlist("study_fields")
        else:
            ids = data.get("study_fields") or data.get("study_fields[]")

        if not ids:
            raise ValidationError("رشته های تحصیلی را وارد کنید!")

        serializer.save()

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

    def perform_update(self, serializer):
        """
        Update a project.

        - PUT: require non-empty study_fields (same rule as create).
        - PATCH: study_fields is optional; if it's present (even empty list),
                the serializer can update/clear it. If it's omitted, leave as-is.
        - Works for both JSON and multipart/form-data.
        - Clears list/homepage caches and a per-project cache key.
        """
        data = self.request.data
        method = self.request.method.upper()

        if hasattr(data, "getlist"):  # multipart/form-data
            ids = data.getlist("study_fields[]") or data.getlist("study_fields")
            provided = ("study_fields[]" in data) or ("study_fields" in data)
        else:                         # application/json
            ids = data.get("study_fields") or data.get("study_fields[]")
            provided = ("study_fields" in data) or ("study_fields[]" in data)

        # Enforce the same requirement as create on full updates
        if method == "PUT" and not ids:
            raise ValidationError("رشته های تحصیلی را وارد کنید!")

        instance = serializer.save()  # serializer will read `study_fields_ids` from context

        # Bust caches
        cache.delete_many([
            "active_projects_list",
            "project_status_stats",
            "homepage_projects",
            f"project_detail_{instance.pk}",
        ])


    # def perform_destroy(self, instance):
    #     """Clear caches after project deletion"""
    #     super().perform_destroy(instance)
        
    #     # Clear related caches
    #     cache.delete_many([
    #         'active_projects_list',
    #         'project_status_stats', 
    #         'homepage_projects'
    #     ])    

def perform_destroy(self, instance):
    # keep IDs/handles you might need after delete
    pk = instance.pk
    image = getattr(instance, "image", None)
    video = getattr(instance, "video", None)
    filef = getattr(instance, "file", None)

    # delete DB row
    super().perform_destroy(instance)

    # OPTIONAL — clean up orphaned media files (ignore storage errors)
    for f in (image, video, filef):
        try:
            if f and hasattr(f, "delete"):
                f.delete(save=False)
        except Exception:
            pass

    # invalidate caches
    cache.delete_many([
        "active_projects_list",
        "project_status_stats",
        "homepage_projects",
        f"project_detail_{pk}",   # object-scoped key if you use one
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
