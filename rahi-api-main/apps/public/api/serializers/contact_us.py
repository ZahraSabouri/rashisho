from rest_framework.serializers import ModelSerializer

from apps.public.models import ContactUs


class ContactUsSerializer(ModelSerializer):
    class Meta:
        model = ContactUs
        fields = "__all__"
