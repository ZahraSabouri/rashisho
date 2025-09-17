from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from apps.api.schema import TaggedAutoSchema
from apps.public.models import Announcement, UserAnnouncementState
from rest_framework import serializers

class AnnouncementOutSer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["id", "title", "body"]

class AnnouncementActionInSer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["remind_later", "got_it"])

class ActiveAnnouncementAV(APIView):
    permission_classes = [IsAuthenticated]
    schema = TaggedAutoSchema(tags=["Announcements"])

    def get(self, request):
        ann = Announcement.objects.filter(active=True).order_by("-created_at").first()
        if not ann:
            return Response(None, status=status.HTTP_200_OK)

        st = UserAnnouncementState.objects.filter(user=request.user, announcement=ann, got_it=True).first()
        if st:
            return Response(None, status=status.HTTP_200_OK)  # already acknowledged
        return Response(AnnouncementOutSer(ann).data, status=status.HTTP_200_OK)

    def post(self, request):
        ann = Announcement.objects.filter(active=True).order_by("-created_at").first()
        if not ann:
            return Response({"detail": "No active announcement."}, status=404)

        ser = AnnouncementActionInSer(data=request.data)
        ser.is_valid(raise_exception=True)

        if ser.validated_data["action"] == "got_it":
            UserAnnouncementState.objects.update_or_create(
                user=request.user, announcement=ann, defaults={"got_it": True}
            )
        # remind_later => do nothing; it will show on next login
        return Response({"ok": True}, status=200)
