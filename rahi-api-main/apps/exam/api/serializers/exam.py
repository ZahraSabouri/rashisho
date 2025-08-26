from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.exam import models, services


class GeneralQuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GeneralQuestionOption
        exclude = ["deleted", "deleted_at", "updated_at", "created_at"]


class GeneralQuestionSerializer(serializers.ModelSerializer):
    general_question_answer = serializers.SerializerMethodField()

    class Meta:
        model = models.GeneralQuestion
        exclude = ["deleted", "deleted_at", "updated_at", "created_at"]

    def get_general_question_answer(self, instance):
        options = instance.general_question_answer.all().order_by("created_at")
        return GeneralQuestionOptionSerializer(options, many=True).data

    def validate(self, attrs):
        score = attrs.get("score", None)
        if not score:
            attrs["score"] = 0

        return super().validate(attrs)

    def create(self, validated_data):
        number = validated_data.get("number", None)
        exam = validated_data.get("exam", None)
        if number and exam:
            if models.GeneralQuestion.objects.filter(exam=exam, number=number).exists():
                raise ValidationError("شماره سوال تکراری است!")

        return super().create(validated_data)


class GeneralExamSerializer(serializers.ModelSerializer):
    general_question_exam = serializers.SerializerMethodField()

    class Meta:
        model = models.GeneralExam
        exclude = ["deleted", "deleted_at", "updated_at", "created_at"]

    def get_general_question_exam(self, obj):
        if self.context["action"] == "list":
            return None
        queryset = models.GeneralQuestion.objects.filter(exam=obj)
        return GeneralQuestionSerializer(queryset, many=True).data

    def validate_mode(self, value):
        if isinstance(self.initial_data, dict):
            if value == "EN" and self.initial_data.get("project") is None:
                raise serializers.ValidationError("در آزمون ورودی انتخاب پروژه اجباری است")
            return value
        raise serializers.ValidationError("خطایی رخ داد")

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # general_exam = []
        # users_count = models.UserAnswer.objects.all().values_list("answer__general__answers", flat=True)
        # for item in users_count:
        #     if not item:
        #         continue
        #     for key in item.keys():
        #         exam = models.GeneralExam.objects.filter(id=key).first()
        #         if exam and exam == instance:
        #             general_exam.append(key)

        # rep["users_count"] = len(general_exam)
        rep["question_count"] = models.GeneralQuestion.objects.filter(exam=instance).count()
        return rep


class UserGeneralQuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GeneralQuestionOption
        exclude = ["deleted", "deleted_at", "updated_at", "created_at", "correct_answer"]


class UserGeneralQuestionSerializer(serializers.ModelSerializer):
    general_question_answer = serializers.SerializerMethodField()

    class Meta:
        model = models.GeneralQuestion
        exclude = ["deleted", "deleted_at", "updated_at", "created_at"]

    def get_general_question_answer(self, instance):
        options = instance.general_question_answer.all().order_by("created_at")
        return UserGeneralQuestionOptionSerializer(options, many=True).data


class UserGeneralExamListSerializer(serializers.ModelSerializer):
    general_question_exam = serializers.SerializerMethodField()

    class Meta:
        model = models.GeneralExam
        exclude = ["deleted", "deleted_at", "updated_at", "created_at"]

    def get_general_question_exam(self, obj):
        if self.context["action"] == "list":
            return None
        queryset = models.GeneralQuestion.objects.filter(exam=obj)
        return UserGeneralQuestionSerializer(queryset, many=True).data

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        user = self.context["request"].user
        exam_pk = self.context["exam_pk"]
        user_answer: models.UserAnswer = models.UserAnswer.objects.filter(user=user).first()
        if user_answer and exam_pk:
            exam: models.GeneralExam = models.GeneralExam.objects.filter(id=exam_pk).first()
            exam_time = exam.time
            user_exam = user_answer.answer["general"]["answers"].get(exam_pk, None)
            if user_exam:
                rep["general_exam_status"] = user_exam["status"]
                remain = services.calc_exam_remain_time(user_exam["started"], exam_time)
                rep["general_exam_remained_time"] = 0 if remain <= 0 else remain

        rep["question_count"] = models.GeneralQuestion.objects.filter(exam=instance).count()

        # general_exam = []
        # users_count = models.UserAnswer.objects.all().values_list("answer__general__answers", flat=True)
        # for item in users_count:
        #     for key in item.keys():
        #         exam = models.GeneralExam.objects.filter(id=key).first()
        #         if not exam:
        #             continue
        #         if exam == instance:
        #             general_exam.append(key)

        # rep["users_count"] = len(general_exam)

        return rep


class GeneralQuestionAnswerSerializer(serializers.Serializer):
    question = serializers.UUIDField()
    answer = serializers.UUIDField()

    def _user_answer(self) -> models.UserAnswer:
        return self.context["user_answer"]

    def validate_question(self, value):
        question = get_object_or_404(models.GeneralQuestion, pk=value)
        if question.exam != self.context["exam"]:
            raise serializers.ValidationError("سوال معتبر نیست")
        return value

    def validate_answer(self, value):
        option = get_object_or_404(models.GeneralQuestionOption, pk=value)
        if isinstance(self.initial_data, dict):
            if str(option.question.pk) != str(self.initial_data["question"]):
                raise serializers.ValidationError("گزینه معتبر نیست")
            if not services.check_valid_time(self._user_answer(), option.question.exam):
                raise serializers.ValidationError("زمان به پایان رسیده است")
        return value

    def create(self, validated_data):
        exam = get_object_or_404(models.GeneralQuestion, pk=validated_data["question"]).exam
        services.save_general_answer(self._user_answer(), services.parse_general_answer(validated_data), exam)
        return validated_data


class GeneralExamSelectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GeneralExam
        fields = ["id", "title"]
