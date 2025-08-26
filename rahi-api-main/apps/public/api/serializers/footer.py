from rest_framework import serializers

from apps.public.models import Footer


class FooterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Footer
        fields = "__all__"
