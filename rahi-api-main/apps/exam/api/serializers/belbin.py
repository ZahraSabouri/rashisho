import functools

from django.core.validators import MaxValueValidator, MinValueValidator
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from apps.exam import models, services


class BelbinAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BelbinAnswer
        exclude = ["deleted", "deleted_at"]
        read_only_fields = ["question"]


class BelbinOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BelbinAnswer
        exclude = ["deleted", "deleted_at"]


class BelbinQuestionSerializer(serializers.ModelSerializer):
    belbin_answer_question = BelbinAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = models.BelbinQuestion
        exclude = ["deleted", "deleted_at"]


class BelbinMultiCreateSerializer(serializers.Serializer):
    question = serializers.DictField()
    answers = serializers.ListField(child=serializers.CharField())

    def create(self, validated_data):
        question = validated_data["question"]
        answers = validated_data["answers"]

        question_serializer = BelbinQuestionSerializer(data=question)
        question_serializer.is_valid(raise_exception=True)
        question_serializer.save()

        created_question = models.BelbinQuestion.objects.filter(number=int(question["number"])).first()

        assert created_question is not None

        for answer in answers:
            data = {"answer": answer, "question": created_question.id}
            serializer = BelbinOptionSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return validated_data


class BelbinMultiUpdateSerializer(serializers.Serializer):
    question = serializers.DictField()
    answers = serializers.ListField(child=serializers.CharField())

    def create(self, validated_data):
        question = validated_data["question"]
        answers = validated_data["answers"]

        instance = get_object_or_404(models.BelbinQuestion, pk=question["id"])
        serializer = BelbinQuestionSerializer(instance=instance, data=question, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        models.BelbinAnswer.objects.filter(question=instance).delete()

        for answer in answers:
            data = {"answer": answer, "question": instance.id}
            serializer = BelbinOptionSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return validated_data


class BelbinUserAnswerSerializer(serializers.Serializer):
    answer = serializers.UUIDField()
    score = serializers.IntegerField(validators=[MaxValueValidator(10), MinValueValidator(0)])

    @functools.cache
    def _question(self) -> models.BelbinQuestion:
        return self.context["question"]

    @functools.cache
    def _user_answer(self) -> models.UserAnswer:
        return self.context["user_answer"]

    @functools.cache
    def _answer(self) -> models.BelbinAnswer:
        if isinstance(self.initial_data, dict):
            answer_id: str = self.initial_data.get("answer")
            return get_object_or_404(models.BelbinAnswer, pk=answer_id, question=self._question())
        raise serializers.ValidationError("جواب معتبر نیست")

    def create(self, validated_data):
        services.save_belbin_answer(self._user_answer(), services.parse_user_answer(validated_data), self._question())
        return validated_data

    def validate_score(self, value):
        if not services.valid_score(self._user_answer(), self._answer(), score=int(value)):
            raise serializers.ValidationError("جمع نمرات نباید بیشتر از 10 شود!")
        return value


class BelbinMultipleUserSerializer(serializers.Serializer):
    question = serializers.UUIDField()
    answers = serializers.ListField(child=serializers.JSONField())

    def create(self, validated_data):
        for answer in validated_data["answers"]:
            self.context["question"] = get_object_or_404(models.BelbinQuestion, pk=validated_data["question"])
            serializer = BelbinUserAnswerSerializer(data=answer, context=self.context)
            if serializer.is_valid():
                serializer.save()
            else:
                raise serializers.ValidationError(serializer.errors)
        return validated_data
