from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.public.api.serializers import footer
from apps.public.models import Footer


class FooterViewSet(ModelViewSet):
    serializer_class = footer.FooterSerializer
    queryset = Footer.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]

    def get_object(self):
        return Footer.objects.first()
