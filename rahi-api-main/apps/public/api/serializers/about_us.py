from rest_framework.serializers import ModelSerializer

from apps.public.models import AboutUs


class AboutUsSerializer(ModelSerializer):
    class Meta:
        model = AboutUs
        fields = "__all__"

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["image"] = instance.image.url if instance.image else None
        return rep
