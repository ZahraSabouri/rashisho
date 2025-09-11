from datetime import datetime, timezone
import jwt
import uuid
from django.db.models import Q

from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.utils.test_tokens import generate_test_token, decode_test_token
from apps.api.roles import Roles
from apps.account.models import User

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework import permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404


from apps.account import models
from apps.account.api.serializers import user as serializer
from apps.account.services import get_sso_user_info
from apps.api.permissions import IsSysgod

from django.conf import settings
from django.contrib.auth.models import Group
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from apps.api.schema import TaggedAutoSchema
from apps.api.pagination import Pagination
from apps.account.api.serializers.user import PublicProfileSerializer
from apps.api.permissions import IsAdminOrReadOnlyPermission


def _ttl_fields_from_token(token: str) -> dict:
    payload = jwt.decode(token, options={"verify_signature": False})
    exp = payload.get("exp")
    now = int(datetime.now(timezone.utc).timestamp())
    return {"expires_at": exp, "ttl_seconds": (exp - now) if exp else None}


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
    queryset = models.User.objects.all()

    def get_object(self):
        return self.request.user


class UserAV(ListAPIView):
    schema = TaggedAutoSchema(tags=["User"])
    serializer_class = serializer.MeSerializer
    queryset = models.User.objects.all()
    permission_classes = [IsAuthenticated, IsSysgod]


class PublicProfileAV(APIView):
    # permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.AllowAny]
    schema = TaggedAutoSchema(tags=["User"])

    @extend_schema(
        # summary="Get public profile (by UUID)",
        parameters=[OpenApiParameter(name="id", type=str, location=OpenApiParameter.PATH, description="User UUID")],
        responses={200: PublicProfileSerializer},
        tags=["User"]
    )
    # def get(self, request, id):
    #     user = User.objects.filter(id=id).first()
    #     if not user:
    #         return Response({"detail": "کاربر یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
    #     data = PublicProfileSerializer(user, context={"request": request}).data
    #     return Response(data, status=status.HTTP_200_OK)
    
    def get(self, request, id):
        user = get_object_or_404(User, id=id, is_active=True)
        ser = PublicProfileSerializer(user, context={"request": request, "include_tests": True})
        return Response(ser.data, status=status.HTTP_200_OK)


class PublicProfileListAV(ListAPIView):
    # permission_classes = [permissions.IsAuthenticated, IsSysgod]
    permission_classes = [permissions.AllowAny]
    schema = TaggedAutoSchema(tags=["User"])
    serializer_class = PublicProfileSerializer
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
        responses={200: PublicProfileSerializer},
    )
    def get_queryset(self):
        qs = (
            models.User.objects.filter(is_active=True)
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
                return models.User.objects.none()

        q = self.request.query_params.get("q")
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(user_info__first_name__icontains=q)
                | Q(user_info__last_name__icontains=q)
                | Q(username__icontains=q)
            )
        return qs
    
    # def get(self, request):
    #     qs = User.objects.filter(is_active=True).order_by("-date_joined")
    #     ser = PublicProfileSerializer(qs, many=True, context={"request": request, "include_tests": False})
    #     return Response(ser.data, status=status.HTTP_200_OK)


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