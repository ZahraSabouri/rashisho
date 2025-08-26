from rest_framework.serializers import ModelSerializer

from apps.public.models import CommonQuestions


class CommonQuestionsSerializer(ModelSerializer):
    class Meta:
        model = CommonQuestions
        fields = "__all__"
