# apps/account/api/views/connection.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from apps.account.api.serializers.connection import (
    ConnectionCreateSerializer,
    ConnectionDecisionSerializer,
    ConnectionSerializer,
)
from apps.account.services import ConnectionService

class ConnectionRequestAV(APIView):
    """
    Presentation لایه (APIView ~ ASP.NET Controller Action)
    POST /api/account/connections/request
    """
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ConnectionService()  # DI دستی

    @extend_schema(
        request=ConnectionCreateSerializer,
        responses={201: OpenApiResponse(response=ConnectionSerializer)},
        tags=["Connections"],
        operation_id="connection_send_request",
        description="ارسال درخواست ارتباط از کاربر لاگین‌شده به کاربر مقصد (status=pending).",
    )
    def post(self, request):
        ser = ConnectionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        conn = self.service.send_request(from_user_id=request.user.id, to_user_id=ser.validated_data["to_user"])
        return Response(ConnectionSerializer(conn).data, status=status.HTTP_201_CREATED)


class PendingConnectionsAV(APIView):
    """
    GET /api/account/connections/pending?box=received|sent
    - پیش‌فرض: هر دو سمت (sent/received) برای کاربر لاگین‌شده
    """
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ConnectionService()

    @extend_schema(
        parameters=[
            OpenApiParameter(name="box", required=False, type=str, description="received | sent | (خالی برای هر دو)"),
        ],
        responses={200: OpenApiResponse(response=ConnectionSerializer)},
        tags=["Connections"],
        operation_id="connection_list_pendings",
        description="لیست درخواست‌های pending کاربر (دریافتی/ارسالی).",
    )
    def get(self, request):
        box = request.query_params.get("box")
        qs = self.service.list_pendings(user_id=request.user.id, box=box)
        data = ConnectionSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)


class ConnectionDecisionAV(APIView):
    """
    POST /api/account/connections/{id}/decision
    body: { "decision": "accepted" | "rejected" }
    فقط گیرنده می‌تواند تصمیم بگیرد.
    """
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ConnectionService()

    @extend_schema(
        request=ConnectionDecisionSerializer,
        responses={200: OpenApiResponse(response=ConnectionSerializer)},
        tags=["Connections"],
        operation_id="connection_decision",
        description="تایید یا رد یک درخواست ارتباط (فقط توسط گیرنده).",
    )
    def post(self, request, id: int):
        ser = ConnectionDecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        conn = self.service.decide(
            connection_id=id,
            actor_user_id=request.user.id,
            decision=ser.validated_data["decision"],
        )
        return Response(ConnectionSerializer(conn).data, status=status.HTTP_200_OK)
