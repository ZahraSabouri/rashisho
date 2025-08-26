from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.public.api.serializers import about_us
from apps.public.models import AboutUs


class AboutUsViewSet(ModelViewSet):
    serializer_class = about_us.AboutUsSerializer
    queryset = AboutUs.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]

    def get_object(self):
        return AboutUs.objects.first()
