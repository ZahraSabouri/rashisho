from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.exam.models import ExamResult


class ExamResultSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(slug_field="full_name", queryset=get_user_model().objects.all())

    class Meta:
        model = ExamResult
        exclude = ["deleted_at", "deleted"]
