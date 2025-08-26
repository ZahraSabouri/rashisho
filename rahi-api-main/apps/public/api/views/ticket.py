from django.db.models import Q
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.api.permissions import IsAdminOrReadOnlyPermission, IsSysgod, IsUser
from apps.public.api.serializers.ticket import CommentSerializer, DepartmentSerializer, TicketSerializer
from apps.public.models import Comment, Department, Ticket
from apps.utils.utility import paginated_response


class CommentViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsSysgod | IsUser]
    filterset_fields = ["ticket", "ticket__status", "user_id"]

    def _user(self):
        return self.request.user

    def get_queryset(self):
        ticket_id = self.request.query_params.get("ticket_id")

        # users can see just their tickets
        if self._user().role == 1:
            user_tickets = Comment.objects.filter(user=self._user()).values_list("ticket", flat=True).distinct()
            return Comment.objects.filter(
                (Q(user=self._user()) | Q(user_role="ADMIN", ticket__in=user_tickets)), ticket=ticket_id
            ).order_by("-created_at")

        # admin can see all tickets under a ticket
        if self._user().role == 0:
            return Comment.objects.filter(ticket=ticket_id).order_by("-created_at")

        return Comment.objects.none()

    def perform_create(self, serializer):
        user_role = self._user().role
        if user_role == 1:
            role = "USER"

        if user_role == 0:
            role = "ADMIN"

        serializer.save(user=self._user(), user_role=role)
        super().perform_create(serializer)

    @action(methods=["get"], detail=False, url_path="close-ticket")
    def close_ticket(self, request, *args, **kwargs):
        """Here admin or user can close a ticket"""

        comment = Comment.objects.filter(ticket_id=self.request.query_params.get("ticket_id"))
        if request.user.role == 1:
            comment = comment.filter(user=self.request.user)

        comment = comment.first()
        if not comment:
            return Response(data={"message": "تیکت یافت نشد!"}, status=status.HTTP_400_BAD_REQUEST)

        comment.ticket.status = "CLOSED"
        comment.ticket.save()
        return Response(data={"message": "با موفقیت انجام شد!"}, status=status.HTTP_200_OK)

    @action(methods=["get"], detail=False, url_path="get_tickets", serializer_class=TicketSerializer)
    def get_tickets(self, request, *args, **kwargs):
        """Returns all ticket for a user"""

        department_id = self.request.query_params.get("department_id", None)
        if self.request.user.role == 0:
            queryset = Ticket.objects.filter(comments__user_role="USER").order_by("-id").distinct()

            if department_id:
                queryset = (
                    Ticket.objects.filter(comments__user_role="USER", department_id=department_id)
                    .order_by("-id")
                    .distinct()
                )

            return paginated_response(self, queryset)

        queryset = Ticket.objects.filter(comments__user=self._user()).order_by("-id").distinct("id")
        return paginated_response(self, queryset)


class DepartmentViewSet(ModelViewSet):
    permission_classes = [IsAdminOrReadOnlyPermission]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
