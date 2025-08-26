from rest_framework.serializers import ModelSerializer

from apps.public.models import ContactInformation


class ContactInformationSerializer(ModelSerializer):
    class Meta:
        model = ContactInformation
        fields = "__all__"

    def update(self, instance, validated_data):
        for field in self.fields:
            if field == "id":
                continue
            if field not in validated_data:
                setattr(instance, field, None)

        return super().update(instance, validated_data)
