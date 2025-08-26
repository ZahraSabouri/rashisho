from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from apps.common.serializers import CustomSlugRelatedField
from apps.public.models import Comment, Department, Ticket


class DepartmentSerializer(ModelSerializer):
    class Meta:
        model = Department
        exclude = ["deleted", "deleted_at"]


class TicketSerializer(ModelSerializer):
    status = serializers.CharField(required=False, allow_null=True)
    department = CustomSlugRelatedField(
        slug_field="title", queryset=Department.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Ticket
        fields = ["id", "title", "status", "department", "user"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["user"] = {"user_id": instance.user.id, "full_name": instance.user.full_name}
        return rep


class CommentSerializer(ModelSerializer):
    user = CustomSlugRelatedField(
        slug_field="full_name", queryset=get_user_model().objects.all(), required=False, allow_null=True
    )
    ticket = CustomSlugRelatedField(slug_field="title", queryset=Ticket.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Comment
        exclude = ["deleted", "deleted_at"]
        read_only_fields = ["user", "user_role"]

    def create(self, validated_data):
        title = self.initial_data.get("title", None)
        department_id = self.initial_data.get("department_id", None)

        ticket = validated_data.get("ticket", None)
        if not ticket:
            if title:
                validated_data["ticket"] = Ticket.objects.create(
                    status="OPEN", title=title, department_id=department_id
                )
            else:
                raise ValidationError("عنوان تیکیت را وارد کنید!")

        comment = Comment.objects.filter(ticket_id=ticket).first()
        if comment:
            user = comment.user

        if ticket and not (self.context["request"].user.role == 0 or self.context["request"].user == user):
            raise ValidationError("مجاز به انجام این عملیات نمی باشید!")

        if Ticket.objects.get(id=validated_data["ticket"].id).status == "CLOSED":
            raise ValidationError("این گفت و گو خاتمه یافته است!")

        return super().create(validated_data)

    def to_representation(self, instance: Comment):
        rep = super().to_representation(instance)
        rep["ticket"] = {"id": instance.ticket.id, "title": instance.ticket.title, "status": instance.ticket.status}
        if instance.ticket.department:
            rep["department"] = {"id": instance.ticket.department.id, "title": instance.ticket.department.title}
        rep["file"] = instance.file.url if instance.file else None
        return rep
