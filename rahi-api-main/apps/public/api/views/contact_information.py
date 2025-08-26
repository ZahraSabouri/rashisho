from rest_framework.viewsets import ModelViewSet

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.public.api.serializers import contact_information
from apps.public.models import ContactInformation


class ContactInformationViewSet(ModelViewSet):
    serializer_class = contact_information.ContactInformationSerializer
    queryset = ContactInformation.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]

    def get_object(self):
        return ContactInformation.objects.first()
