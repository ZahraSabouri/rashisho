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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from apps.utils.test_tokens import generate_test_token


@api_view(['GET'])
@permission_classes([AllowAny])
def dev_token_view(request):
    """Generate test token for development - DEV ONLY"""
    if not settings.DEBUG:
        return Response({"error": "Only available in DEBUG mode"}, status=403)
    
    token = generate_test_token()
    return Response({
        "token": token, 
        "usage": f"Bearer {token}",
        "note": "Use this token in Authorization header for API calls"
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