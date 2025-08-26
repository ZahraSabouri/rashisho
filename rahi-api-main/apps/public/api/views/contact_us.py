from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsSysgod
from apps.public.api.serializers import contact_us
from apps.public.models import ContactUs


class ContactUsViewSet(ModelViewSet):
    serializer_class = contact_us.ContactUsSerializer
    queryset = ContactUs.objects.all()
    permission_classes = [IsSysgod]
    pagination_class = None

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return super().get_permissions()
