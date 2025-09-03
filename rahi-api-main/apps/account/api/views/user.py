from datetime import datetime, timezone
import jwt

from drf_spectacular.utils import extend_schema

from apps.utils.test_tokens import generate_test_token, decode_test_token
from apps.api.roles import Roles
from apps.account.models import User

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.account import models
from apps.account.api.serializers import user as serializer
from apps.account.services import get_sso_user_info
from apps.api.permissions import IsSysgod

from django.conf import settings
from django.contrib.auth.models import Group
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from apps.utils.test_tokens import generate_test_token, decode_test_token
from apps.api.roles import Roles
from apps.account.models import User

from datetime import datetime, timezone
import jwt
from django.conf import settings
from django.contrib.auth.models import Group
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.utils.test_tokens import generate_test_token, decode_test_token
from apps.api.roles import Roles
from apps.account.models import User


def _ttl_fields_from_token(token: str) -> dict:
    """Return {'expires_at': <unix ts>, 'ttl_seconds': <int>} without verifying signature."""
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
    serializer_class = serializer.MeSerializer
    queryset = models.User.objects.all()

    def get_object(self):
        return self.request.user


class UserAV(ListAPIView):
    serializer_class = serializer.MeSerializer
    queryset = models.User.objects.all()
    permission_classes = [IsAuthenticated, IsSysgod]


class UpdateInfo(APIView):
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

    def patch(self, request, *args, **kwargs):
        self.request.user.is_accespted_terms = True
        self.request.user.save()
        return Response()