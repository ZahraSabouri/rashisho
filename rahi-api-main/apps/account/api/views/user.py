from datetime import datetime, timezone
import jwt
import uuid
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from django.conf import settings
from django.contrib.auth.models import Group

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse

from rest_framework import status, permissions
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes

from apps.utils.test_tokens import generate_test_token, decode_test_token
from apps.api.roles import Roles
from apps.api.permissions import IsSysgod
from apps.api.schema import TaggedAutoSchema
from apps.api.pagination import Pagination

from apps.account.models import User, PeerFeedback
from apps.account.services import get_sso_user_info
from apps.account.api.serializers import user as serializer

from apps.project.models import ProjectAttractiveness
from apps.project.api.serializers.project import ProjectListSerializer  # reuse (id, title)

from apps.project.models import TeamRequest


def _ttl_fields_from_token(token: str) -> dict:
    payload = jwt.decode(token, options={"verify_signature": False})
    exp = payload.get("exp")
    now = int(datetime.now(timezone.utc).timestamp())
    return {"expires_at": exp, "ttl_seconds": (exp - now) if exp else None}


def _are_current_teammates(a: User, b: User) -> bool:
    if not a or not b or a.id == b.id:
        return False
    my_team_ids = TeamRequest.objects.filter(user=a, status="A").values_list("team_id", flat=True)
    return TeamRequest.objects.filter(user=b, status="A", team_id__in=my_team_ids).exists()



# --- USER TOKEN ---
@extend_schema(tags=["DEV Tools"], description="Generate a development USER token (DEBUG only).")
@api_view(["GET"])
@permission_classes([AllowAny])
def dev_user_token_view(request):
    if not settings.DEBUG:
        return Response({"error": "Only available in DEBUG mode"}, status=403)

    token = generate_test_token()
    user_id = decode_test_token(token)

    user, _ = User.objects.get_or_create(
        user_info__id=user_id,
        defaults={
            "username": f"user_{user_id[:8]}",
            "email": f"user_{user_id[:8]}@test.com",
            "user_info": {
                "id": user_id, "first_name": f"User{user_id[:4]}", "last_name": "Test",
                "national_id": None, "mobile_number": f"0912345{user_id[:4]}",
            },
        },
    )

    user_role, _ = Group.objects.get_or_create(name=Roles.user.name)
    user.groups.set([user_role])

    return Response({
        "token": token,
        "usage": f"Bearer {token}",
        "role": "user",
        "user_id": user_id,
        "username": user.username,
        "full_name": user.full_name,
        **_ttl_fields_from_token(token),   # <— TTL/expiry
    })


# --- ADMIN TOKEN ---
@extend_schema(tags=["DEV Tools"], description="Generate a development ADMIN token (DEBUG only).")
@api_view(["GET"])
@permission_classes([AllowAny])
def dev_admin_token_view(request):
    if not settings.DEBUG:
        return Response({"error": "Only available in DEBUG mode"}, status=403)

    token = generate_test_token()
    user_id = decode_test_token(token)

    user, _ = User.objects.get_or_create(
        user_info__id=user_id,
        defaults={
            "username": f"admin_{user_id[:8]}",
            "email": f"admin_{user_id[:8]}@test.com",
            "is_staff": True,
            "is_superuser": True,
            "user_info": {
                "id": user_id, "first_name": f"Admin{user_id[:4]}", "last_name": "Test",
                "national_id": None, "mobile_number": f"0911234{user_id[:4]}",
            },
        },
    )

    admin_role, _ = Group.objects.get_or_create(name=Roles.sys_god.name)
    user.groups.set([admin_role])

    return Response({
        "token": token,
        "usage": f"Bearer {token}",
        "role": "admin",
        "user_id": user_id,
        "username": user.username,
        "full_name": user.full_name,
        **_ttl_fields_from_token(token),   # <— TTL/expiry
    })


class MeAV(RetrieveUpdateAPIView):
    schema = TaggedAutoSchema(tags=["User"])
    serializer_class = serializer.MeSerializer
    queryset = User.objects.all()

    def get_object(self):
        return self.request.user


class UserAV(ListAPIView):
    schema = TaggedAutoSchema(tags=["User"])
    serializer_class = serializer.MeSerializer
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsSysgod]


class PublicProfileAV(APIView):
    # permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.AllowAny]
    schema = TaggedAutoSchema(tags=["User"])

    @extend_schema(
        # summary="Get public profile (by UUID)",
        parameters=[OpenApiParameter(name="id", type=str, location=OpenApiParameter.PATH, description="User UUID")],
        responses={200: serializer.PublicProfileSerializer},
        tags=["User"]
    )
    # def get(self, request, id):
    #     user = User.objects.filter(id=id).first()
    #     if not user:
    #         return Response({"detail": "کاربر یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
    #     data = serializer.PublicProfileSerializer(user, context={"request": request}).data
    #     return Response(data, status=status.HTTP_200_OK)
    
    def get(self, request, id):
        user = get_object_or_404(User, id=id, is_active=True)
        ser = serializer.PublicProfileSerializer(user, context={"request": request, "include_tests": True})
        return Response(ser.data, status=status.HTTP_200_OK)


class PublicProfileListAV(ListAPIView):
    # permission_classes = [permissions.IsAuthenticated, IsSysgod]
    permission_classes = [permissions.AllowAny]
    schema = TaggedAutoSchema(tags=["User"])
    serializer_class = serializer.PublicProfileSerializer
    pagination_class = Pagination

    @extend_schema(
        summary="List public profiles (admin)",
        parameters=[
            OpenApiParameter(
                name="ids", type=str, description="Comma-separated user UUIDs to filter. Optional."
            ),
            OpenApiParameter(
                name="q", type=str, description="Search by first/last name or username. Optional."
            ),
            OpenApiParameter(name="page", type=int, required=False, description="Page number"),
            OpenApiParameter(name="page_size", type=int, required=False, description="Items per page"),
        ],
        responses={200: serializer.PublicProfileSerializer},
    )
    def get_queryset(self):
        qs = (
            User.objects.filter(is_active=True)
            .select_related("city__province")
            .prefetch_related(
                "resume__educations",
                "resume__jobs",
                "resume__certificates",
                "resume__skills",
            )
            .order_by("-created_at")
        )
        ids_param = self.request.query_params.get("ids")
        if ids_param:
            import uuid
            try:
                id_list = [uuid.UUID(x.strip()) for x in ids_param.split(",") if x.strip()]
                qs = qs.filter(id__in=id_list)
            except ValueError:
                return User.objects.none()

        q = self.request.query_params.get("q")
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(user_info__first_name__icontains=q)
                | Q(user_info__last_name__icontains=q)
                | Q(username__icontains=q)
            )
        return qs
    

class PublicUserProjectAttractionsAV(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["User"],
        parameters=[
            OpenApiParameter(
                name="limit", required=False, type=int, location=OpenApiParameter.QUERY,
                description="Max number of items (default 5, max 20)"
            )
        ],
        responses={200: ProjectListSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Sample",
                value=[{"id": "11111111-1111-1111-1111-111111111111", "title": "پروژه نمونه"}]
            )
        ],
    )
    def get(self, request, id):
        user = get_object_or_404(User, id=id)

        try:
            limit = int(request.query_params.get("limit", 5))
        except ValueError:
            limit = 5
        limit = max(1, min(limit, 20))

        rows = (
            ProjectAttractiveness.objects
            .filter(user=user)
            .select_related("project")
            .order_by("-created_at")[:limit]
        )
        projects = [row.project for row in rows]

        data = ProjectListSerializer(projects, many=True, context={"request": request}).data
        return Response(data)


class MeProjectAttractionsAV(APIView):
    permission_classes = [IsAuthenticated]
    schema = TaggedAutoSchema(tags=["User"])

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 5))
        except ValueError:
            limit = 5

        qs = (
            ProjectAttractiveness.objects
            .filter(user=request.user)
            .select_related("project")
            .order_by("-created_at")[:limit]
        )
        projects = [pa.project for pa in qs]
        data = ProjectListSerializer(projects, many=True, context={"request": request}).data
        return Response({"results": data})


class UpdateInfo(APIView):
    schema = TaggedAutoSchema(tags=["User"])
    serializer_class = serializer.MeSerializer

    def get(self, request):
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().filter(id=request.user.id).first()
            token = str(request.META["HTTP_AUTHORIZATION"]).split(" ")[1]
            user.user_info = get_sso_user_info(token)
            user.save()
        return Response(
            data=self.serializer_class(user, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class AcceptTerms(APIView):
    schema = TaggedAutoSchema(tags=["User"])

    def patch(self, request, *args, **kwargs):
        self.request.user.is_accespted_terms = True
        self.request.user.save()
        return Response()
    

class MirrorFeedbackListAV(ListAPIView):
    # permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        if getattr(self.request, "method", "GET").upper() == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]
    permission_classes = [permissions.IsAuthenticated]
    schema = TaggedAutoSchema(tags=["User"])
    serializer_class = serializer.PeerFeedbackPublicSerializer
    pagination_class = Pagination

    @extend_schema(
        # summary="List peer feedback (Mirror) for a user",
        tags=["User"],
        parameters=[
            OpenApiParameter(name="id", type=str, location=OpenApiParameter.PATH, description="User UUID"),
            OpenApiParameter(name="page", type=int, required=False),
            OpenApiParameter(name="page_size", type=int, required=False),
        ],
        responses={200: serializer.PeerFeedbackPublicSerializer},
    )
    def get_queryset(self):
        get_object_or_404(User, id=self.kwargs["id"], is_active=True)
        return (
            PeerFeedback.objects
            .filter(to_user_id=self.kwargs["id"], is_public=True)
            .select_related("author")
            .order_by("-created_at")
        )

    @extend_schema(
        # summary="Create a peer feedback (Mirror) for a user",
        tags=["User"],
        request=serializer.PeerFeedbackCreateSerializer,
        responses={201: OpenApiResponse(response=serializer.PeerFeedbackPublicSerializer)},
        description="Authenticated users can leave peer feedback on another user's profile. "
                    "The created item may be hidden later by admin via Django admin.",
    )
    def post(self, request, *args, **kwargs):
        target_id = self.kwargs["id"]
        target = get_object_or_404(User, id=target_id, is_active=True)
        if str(request.user.id) == str(target.id):
            return Response({"detail": "نمی‌توانید برای خودتان نظر ثبت کنید."},
                            status=status.HTTP_400_BAD_REQUEST)

        create_ser = serializer.PeerFeedbackCreateSerializer(data=request.data)
        create_ser.is_valid(raise_exception=True)

        obj = PeerFeedback.objects.create(
            to_user=target,
            author=request.user,
            **create_ser.validated_data
        )
        out = serializer.PeerFeedbackPublicSerializer(obj, context={"request": request}).data
        return Response(out, status=status.HTTP_201_CREATED)

# class MirrorFeedbackListAV(APIView):
#     permission_classes = [permissions.IsAuthenticated]
#     schema = TaggedAutoSchema(tags=["User"])

#     @extend_schema(
#         request=serializer.PeerFeedbackCreateSerializer,
#         responses={
#             201: OpenApiResponse(response=serializer.PeerFeedbackMineSerializer),
#             403: OpenApiResponse(description="Only teammates can submit Mirror for each other."),
#         },
#         description="Create a Mirror (آیینه‌شو) for a user. "
#                     "⚠️ Allowed only if you and the target user are in the same active team.",
#         tags=["User"],
#     )
#     def post(self, request, id):
#         to_user = get_object_or_404(User, id=id, is_active=True)

#         # ✅ NEW: enforce teammate-only rule
#         if not _are_current_teammates(request.user, to_user):
#             return Response(
#                 {"detail": "فقط اعضای تیم می‌توانند برای هم «آیینه‌شو» ثبت کنند."},
#                 status=status.HTTP_403_FORBIDDEN,
#             )

#         if request.user.id == to_user.id:
#             return Response({"detail": "شما نمی‌توانید برای خودتان نظر ثبت کنید."}, status=status.HTTP_400_BAD_REQUEST)

#         ser = serializer.PeerFeedbackCreateSerializer(data=request.data, context={"request": request})
#         ser.is_valid(raise_exception=True)

#         obj = PeerFeedback.objects.create(
#             author=request.user,
#             to_user=to_user,
#             text=ser.validated_data["text"],
#             phase=ser.validated_data.get("phase", ""),
#             is_public=ser.validated_data.get("is_public", True),
#         )
#         out = serializer.PeerFeedbackMineSerializer(obj, context={"request": request}).data
#         return Response(out, status=status.HTTP_201_CREATED)


class MyMirrorFeedbackAV(ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = TaggedAutoSchema(tags=["User"])
    serializer_class = serializer.PeerFeedbackMineSerializer
    pagination_class = Pagination

    @extend_schema(
        # summary="List my authored Mirror feedbacks",
        tags=["User"],
        responses={200: serializer.PeerFeedbackMineSerializer},
    )
    def get_queryset(self):
        return (
            PeerFeedback.objects
            .filter(author_id=self.request.user.id)
            .select_related("to_user")
            .order_by("-created_at")
        )


class MirrorFeedbackDetailAV(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = TaggedAutoSchema(tags=["User"])

    def _get_obj(self, id: int) -> PeerFeedback:
        return get_object_or_404(PeerFeedback, id=id)

    def _check_actor(self, request, obj: PeerFeedback):
        is_admin = bool(getattr(request.user, "role", None) == 0 or request.user.is_staff or request.user.is_superuser)
        if not (is_admin or obj.author_id == request.user.id):
            return Response({"detail": "اجازه دسترسی ندارید."}, status=status.HTTP_403_FORBIDDEN)

    @extend_schema(
        # summary="Edit my Mirror feedback",
        tags=["User"],
        request=serializer.PeerFeedbackUpdateSerializer,
        responses={200: OpenApiResponse(response=serializer.PeerFeedbackMineSerializer)},
        parameters=[OpenApiParameter(name="id", type=int, location=OpenApiParameter.PATH)],
    )
    def patch(self, request, id: int):
        obj = self._get_obj(id)
        deny = self._check_actor(request, obj)
        if deny: return deny
        ser = serializer.PeerFeedbackUpdateSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        out = serializer.PeerFeedbackMineSerializer(obj, context={"request": request}).data
        return Response(out, status=status.HTTP_200_OK)

    @extend_schema(
        # summary="Delete my Mirror feedback",
        tags=["User"],
        parameters=[OpenApiParameter(name="id", type=int, location=OpenApiParameter.PATH)],
        responses={204: None},
    )
    def delete(self, request, id: int):
        obj = self._get_obj(id)
        deny = self._check_actor(request, obj)
        if deny: return deny
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class AdminUserAttractionsByNationalIDAV(APIView):
    schema = TaggedAutoSchema(tags=["User"])
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, national_id):
        user = get_user_model().objects.filter(user_info__national_id=national_id).first()
        if not user:
            return Response({"detail": "کاربر یافت نشد"}, status=status.HTTP_404_NOT_FOUND)
        qs = ProjectAttractiveness.objects.filter(user=user).select_related("project").order_by("priority", "-project__created_at")
        return Response(ProjectListSerializer([x.project for x in qs], many=True).data, status=status.HTTP_200_OK)