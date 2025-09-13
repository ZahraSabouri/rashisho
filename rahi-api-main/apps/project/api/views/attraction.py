from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.api.schema import TaggedAutoSchema
from apps.project.models import Project, ProjectAttractiveness
from apps.project.api.serializers.project import ProjectListSerializer
from apps.project.api.serializers.attraction import (
    AttractionCreateSerializer, AttractionReorderSerializer
)
from apps.project import services

MAX_ITEMS = 5

class MyAttractionsAV(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = TaggedAutoSchema(tags=["Project Attractions"])

    @extend_schema(
        tags=["Project Attractions"],
        responses={200: ProjectListSerializer(many=True)},
        operation_id="my_attractions_list",
        description="List my attractive projects (ordered by priority, then newest).",
    )
    def get(self, request):
        rows = (
            ProjectAttractiveness.objects
            .filter(user=request.user)
            .select_related("project")
            .order_by("priority", "-created_at")
        )
        projects = [r.project for r in rows]
        data = ProjectListSerializer(projects, many=True, context={"request": request}).data
        return Response({"results": data}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Project Attractions"],
        request=AttractionCreateSerializer,
        responses={201: OpenApiResponse(response=None)},
        operation_id="my_attractions_add",
        description="Add a project to my attractions (or update its priority). Max 5 distinct projects.",
    )
    @transaction.atomic
    def post(self, request):
        ser = AttractionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        project_id = ser.validated_data["project"]
        wanted_priority = ser.validated_data.get("priority")

        # upsert
        obj, created = ProjectAttractiveness.objects.select_for_update().get_or_create(
            user=request.user, project_id=project_id, defaults={}
        )

        # enforce max 5
        mine = ProjectAttractiveness.objects.filter(user=request.user)
        distinct_count = mine.values("project").distinct().count()
        if created and distinct_count > MAX_ITEMS:
            obj.delete()
            return Response(
                {"detail": f"Maximum {MAX_ITEMS} projects allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if wanted_priority:
            # if that slot is occupied by another project, swap to keep logic simple
            clash = mine.filter(priority=wanted_priority).exclude(project_id=project_id).first()
            if clash:
                clash.priority = obj.priority or clash.priority
                clash.priority, obj.priority = obj.priority or wanted_priority, wanted_priority
                clash.save(update_fields=["priority", "updated_at"])
            else:
                obj.priority = wanted_priority
        else:
            # if no priority provided, put it at the end (first free slot 1..5 or leave None)
            occupied = set(mine.exclude(id=obj.id).values_list("priority", flat=True))
            free_slots = [p for p in range(1, MAX_ITEMS + 1) if p not in occupied]
            if free_slots:
                obj.priority = obj.priority or free_slots[0]

        obj.save(update_fields=["priority", "updated_at"])
        return Response(status=status.HTTP_201_CREATED)


class MyAttractionsReorderAV(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = TaggedAutoSchema(tags=["Project Attractions"])

    @extend_schema(
        tags=["Project Attractions"],
        request=AttractionReorderSerializer,
        responses={200: OpenApiResponse(response=None)},
        operation_id="my_attractions_reorder",
        description="Reorder my attractive projects. The list you send becomes priorities 1..n.",
    )
    @transaction.atomic
    def patch(self, request):
        if not services.can_select_projects():
            return Response({"detail": "مرحله انتخاب فعال نیست"}, status=status.HTTP_423_LOCKED)
        ser = AttractionReorderSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)

        ordered_ids = ser.validated_data["projects"]
        mine = (
            ProjectAttractiveness.objects
            .select_for_update()
            .filter(user=request.user, project_id__in=ordered_ids)
        )
        priority_map = {pid: i + 1 for i, pid in enumerate(ordered_ids)}
        for row in mine:
            row.priority = priority_map.get(row.project_id, row.priority)
            row.save(update_fields=["priority", "updated_at"])
        return Response(status=status.HTTP_200_OK)


class MyAttractionDeleteAV(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = TaggedAutoSchema(tags=["Project Attractions"])
    

    @extend_schema(
        tags=["Project Attractions"],
        responses={204: OpenApiResponse(response=None)},
        operation_id="my_attractions_delete",
        description="Remove one project from my attractions.",
    )
    @transaction.atomic
    def delete(self, request, project_id):
        if not services.can_select_projects():
            return Response({"detail": "مرحله انتخاب فعال نیست"}, status=status.HTTP_423_LOCKED)
        ProjectAttractiveness.objects.filter(user=request.user, project_id=project_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
