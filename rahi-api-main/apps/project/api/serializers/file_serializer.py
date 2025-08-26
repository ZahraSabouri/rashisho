from rest_framework import serializers


class ImportFileSerializer(serializers.Serializer):
    file = serializers.FileField(required=True, allow_empty_file=False)
