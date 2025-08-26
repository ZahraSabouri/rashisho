import functools
from datetime import datetime
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status, views
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import CreateModelMixin, ListModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.api import permissions
from apps.api.pagination import Pagination
from apps.exam import models
from apps.exam.api.filters import general
from apps.exam.api.serializers import exam as serializers
from apps.exam.services import (
    calculate_general_exam_score,
    create_general_option,
    create_general_question,
    finish_general_answer,
    update_general_option,
    update_general_question,
)
from apps.resume.models import Resume


class GeneralExamVS(ModelViewSet):
    queryset = models.GeneralExam.objects.prefetch_related(
        Prefetch("general_question_exam", queryset=models.GeneralQuestion.objects.order_by("number"))
    ).all()
    serializer_class = serializers.GeneralExamSerializer
    permission_classes = [permissions.ResumeFinishedPermission]
    filterset_class = general.EntranceExamFilterSet

    def get_permissions(self):
        if self.action in [
            "create",
            "destroy",
            "update",
            "partial_update",
            "create_question_option",
            "update_question_option",
            "delete_question_option",
        ]:
            return [permissions.IsSysgod()]

        return super().get_permissions()

    def get_serializer_class(self):
        if self.request.user.role == 1:
            return serializers.UserGeneralExamListSerializer
        return serializers.GeneralExamSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        context["exam_pk"] = self.kwargs.get("pk", None)
        context["action"] = self.action
        return context

    @functools.cache
    def _user_answer(self):
        return models.UserAnswer.objects.filter(user=self.request.user).first()

    @action(detail=True, methods=["GET"])
    def start_exam(self, request, *args, **kwargs):
        """For register the start time of each general exam for a user"""

        exam = get_object_or_404(models.GeneralExam, id=kwargs["pk"])
        user_answer, _ = models.UserAnswer.objects.get_or_create(user=self.request.user)
        general_answer = user_answer.answer["general"]["answers"]

        if not general_answer.get(f"{exam.id}", None):
            general_answer.update({f"{exam.id}": {}})
            general_answer[f"{exam.id}"]["started"] = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
            general_answer[f"{exam.id}"]["status"] = "started"

            user_answer.save()
            return Response({"message": "آزمون شروع شد!"}, status=status.HTTP_200_OK)

        return Response({"message": "این آزمون قبلا شروع شده است!"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["GET"])
    def end_exam(self, request, *args, **kwargs):
        """For register the end time of each general exam for a user"""

        exam = get_object_or_404(models.GeneralExam, id=kwargs["pk"])
        user_answer, _ = models.UserAnswer.objects.get_or_create(user=self.request.user)
        finish_status = finish_general_answer(user_answer, exam)
        if finish_status:
            return Response({"message": "آزمون به پایان رسید."}, status=status.HTTP_200_OK)

        return Response({"message": "خطایی رخ داده است!"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["POST"], url_path="create-question-option")
    def create_question_option(self, request, *args, **kwargs):
        """For creating a question and its options at same time"""

        question_data = self.request.data["question"]
        option_data = self.request.data["options"]
        if not option_data:
            return Response({"message": "گزینه ها را وراد کنید!"}, status=status.HTTP_400_BAD_REQUEST)

        question = create_general_question(UUID(kwargs["pk"]), question_data, serializers.GeneralQuestionSerializer)
        options = create_general_option(option_data, question, serializers.GeneralQuestionOptionSerializer)
        if not options["status"]:
            models.GeneralQuestion.objects.filter(id=question.id).delete()
            return Response({"errors": options["detail"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "با موفقیت ایجاد شد.", "data": options["data"]}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["POST"], url_path="update-question-option")
    def update_question_option(self, request, *args, **kwargs):
        """For updating a question and its options at same time"""

        question_data = self.request.data["question"]
        option_data = self.request.data["options"]
        if not option_data:
            raise ValidationError("گزینه ها را وراد کنید!")

        question = update_general_question(UUID(kwargs["pk"]), question_data, serializers.GeneralQuestionSerializer)
        options = update_general_option(question, option_data, serializers.GeneralQuestionOptionSerializer)
        if not options["status"]:
            return Response({"errors": options["detail"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "با موفقیت ویرایش شد.", "data": options["data"]}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["delete"], url_path="delete-question-option/(?P<pk>[^/.]+)")
    def delete_question_option(self, request, *args, **kwargs):
        question = get_object_or_404(models.GeneralQuestion, id=kwargs["pk"])
        question.delete()
        return Response({"message": "عملیات با موفقیت انجام شد!"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["GET"], url_path="get-answer")
    def get_user_answer(self, request, *args, **kwargs):
        exam_id = kwargs["pk"]
        user_answer = self._user_answer()
        if not user_answer:
            return Response({"error": "برای این کاربر پاسخی ثبت نشده است!"}, status=status.HTTP_400_BAD_REQUEST)

        user_answer = user_answer.answer["general"]["answers"]
        general_answer = user_answer.get(f"{exam_id}", None)
        if not general_answer:
            return Response({"error": "کاربر در این آزمون پاسخی ثبت نکرده است!"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(general_answer, status=status.HTTP_200_OK)

    @action(detail=True, methods=["GET"], url_path="get-exam-status")
    def get_exam_status(self, request, *args, **kwargs):
        exam_id = kwargs["pk"]
        exam_obj = get_object_or_404(models.GeneralExam, id=exam_id)
        questions_count = models.GeneralQuestion.objects.filter(exam=exam_obj).count()
        user_answer = self._user_answer()

        if not user_answer:
            data = {
                "id": exam_id,
                "title": exam_obj.title,
                "time": exam_obj.time,
                "questions_count": questions_count,
            }
            return Response({"data": data}, status=status.HTTP_200_OK)

        general_answer = user_answer.answer["general"]["answers"].get(f"{exam_id}", None)
        result = {
            "id": exam_id,
            "title": exam_obj.title,
            "time": exam_obj.time,
            "status": general_answer["status"] if general_answer else None,
            "questions_count": questions_count,
        }
        return Response({"data": result}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["GET"], url_path="user_exams")
    def user_exams(self, request, *args, **kwargs):
        """Returns user General and Entrance Exam"""

        resume_id = self.request.query_params.get("resume_id")
        resume = Resume.objects.filter(id=resume_id).first()
        if not resume:
            return Response(data={"رزومه یافت نشد!"}, status=status.HTTP_400_BAD_REQUEST)

        _user = resume.user
        user_answer = models.UserAnswer.objects.filter(user=_user).first()
        result = []
        if user_answer:
            exams = user_answer.answer["general"]["answers"].keys()
            for exam_id in exams:
                exam = models.GeneralExam.objects.filter(id=exam_id).first()
                if not exam:
                    continue
                result.append({"id": exam_id, "title": exam.title, "type": exam.mode})

        return Response(result, status=status.HTTP_200_OK)


class GeneralQuestionAnswerVS(GenericViewSet, CreateModelMixin, ListModelMixin):
    serializer_class = serializers.GeneralQuestionAnswerSerializer
    permission_classes = [permissions.ResumeFinishedPermission, permissions.StartedExamPermission]

    @functools.cache
    def _user_answer(self):
        answer, _ = models.UserAnswer.objects.get_or_create(user=self.request.user)
        return answer

    @functools.cache
    def _exam(self) -> models.GeneralExam:
        return get_object_or_404(models.GeneralExam, pk=self.kwargs["exam_pk"])

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user_answer"] = self._user_answer()
        context["exam"] = self._exam()
        return context

    def list(self, request, *args, **kwargs):
        data = self._user_answer().get_general_by_exam(self._exam())
        total_score = calculate_general_exam_score(self._user_answer(), self._exam())
        data.update({"total_score": total_score})
        return Response(data)


class GeneralExamUsersInfo(views.APIView):
    permission_classes = [permissions.IsSysgod]

    def get(self, request, pk):
        exam = models.GeneralExam.objects.get(id=pk)
        general_users = []
        users = models.UserAnswer.objects.all().values_list("answer__general__answers", "user")

        for item in users:
            for key, value in item[0].items():
                if key == str(exam.id) and value["status"] == "finished":
                    general_users.append(item[1])

        users_list = []
        for user_id in general_users:
            user = get_user_model().objects.filter(id=user_id).first()
            if not user:
                continue
            users_list.append({"full_name": user.full_name, "national_id": user.user_info.get("national_id", None)})

        return Response({"users_list": users_list}, status=status.HTTP_200_OK)


class GeneralExamSelectAPV(views.APIView, Pagination):
    serializer_class = serializers.GeneralExamSelectSerializer
    permission_classes = [permissions.IsSysgod | permissions.IsSysgod]

    def get(self, request):
        exam_type = request.query_params.get("mode", None)
        exams = models.GeneralExam.objects.all()
        if exam_type:
            exams = models.GeneralExam.objects.filter(mode=exam_type)

        result = self.paginate_queryset(exams, request, view=self)
        serializer = self.serializer_class(result, many=True)
        return self.get_paginated_response(serializer.data)
