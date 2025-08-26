from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from apps.exam import models
from apps.exam.models import default_neo_options
from apps.exam.services import save_neo_answer


class NeoQuestionSerializer(ModelSerializer):
    class Meta:
        model = models.NeoQuestion
        exclude = ["deleted", "deleted_at"]


class NeoOptionSerializer(ModelSerializer):
    class Meta:
        model = models.NeoOption
        exclude = ["deleted", "deleted_at"]
        read_only_fields = ["question"]


class NeoUserAnswerSerializer(serializers.Serializer):
    answer = serializers.ChoiceField(choices=default_neo_options())

    def create(self, validated_data):
        validated_data["answer"] = str(validated_data["answer"])
        user_answer_obj: models.UserAnswer = self.context["user_answer"]
        question_obj = self.context["question"]
        save_neo_answer(user_answer_obj, question_obj, validated_data["answer"])
        return validated_data
