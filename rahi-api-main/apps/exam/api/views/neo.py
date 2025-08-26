import functools
from uuid import UUID

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, ListModelMixin
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.api.permissions import IsAdminOrReadOnlyPermission, IsSysgod, IsUser, NeoPermission, ResumeFinishedPermission
from apps.exam import models
from apps.exam.api.serializers import neo
from apps.exam.services import check_user_next_question, get_question, user_neo_score
from apps.utils.utility import CustomModelViewSet


class NeoQuestionViewSet(CustomModelViewSet):
    serializer_class = neo.NeoQuestionSerializer
    queryset = models.NeoQuestion.objects.all().order_by("number")
    permission_classes = [IsAdminOrReadOnlyPermission, NeoPermission]

    @action(methods=["get"], detail=False, permission_classes=[IsUser | IsSysgod])
    def neo_user_next_question(self, request, *args, **kwargs):
        """Here we check the user answers and return him the next question."""
        question = check_user_next_question(user=self.request.user, exam="neo", model=models.NeoQuestion)
        serializer = self.serializer_class(question)
        return Response(serializer.data)

    @action(methods=["post"], detail=False)
    def change_options(self, request, *args, **kwargs):
        """For update options field for all NeoQuestion's objects"""

        new_options = self.request.data.get("options", None)

        if not isinstance(new_options, dict):
            return Response({"detail": "باید دیکشنری ارسال شود!"}, status=status.HTTP_400_BAD_REQUEST)

        questions = models.NeoQuestion.objects.all()

        if not questions:
            return Response({"detail": "هیچ سوالی برای آزمون نئو وجود ندارد!"}, status=status.HTTP_400_BAD_REQUEST)

        for question in questions:
            question.options.update(new_options)
            question.save()

        return Response({"detail": "عملیات با موفقیت انجام شد."}, status=status.HTTP_200_OK)

    @action(methods=["get"], detail=True, url_path="get-question", permission_classes=[IsUser | IsSysgod])
    def get_next_or_previous_question(self, request, *args, **kwargs):
        """Here we return the next question or the previous question."""

        state = self.request.query_params.get("state", None)
        current_question = get_object_or_404(models.NeoQuestion, id=kwargs["pk"])

        question = get_question(current_question, "neo", state)

        if question and isinstance(question, models.NeoQuestion):
            serializer = self.serializer_class(question)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "سوال ها به پایان رسیده است!"}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["get"], detail=True, url_path="answer-by-question", permission_classes=[IsUser | IsSysgod])
    def get_user_answer_by_question(self, request, *args, **kwargs):
        """Here we return the user answer for one question."""

        question = get_object_or_404(models.NeoQuestion, id=kwargs["pk"])
        _user = self.request.user
        user_answer = models.UserAnswer.objects.filter(user=_user).first()
        if not user_answer:
            return Response("کاربر پاسخی ثبت نکرده است!")

        neo_answer = user_answer.answer["neo"]["answers"]

        for key, value in neo_answer.items():
            if UUID(key) == question.id:
                return Response(value)

        return Response(status=status.HTTP_400_BAD_REQUEST)


class NeoOptionViewSet(ModelViewSet):
    serializer_class = neo.NeoOptionSerializer
    queryset = models.NeoOption.objects.all().order_by("option_number")
    permission_classes = [IsAdminOrReadOnlyPermission, NeoPermission]

    def _question(self):
        question = get_object_or_404(models.NeoQuestion, pk=self.kwargs["neo_pk"])
        return question

    def perform_create(self, serializer):
        serializer.save(question=self._question())
        super().perform_create(serializer)


class NeoUserAnswerViewSet(GenericViewSet, CreateModelMixin, ListModelMixin):
    serializer_class = neo.NeoUserAnswerSerializer
    permission_classes = [ResumeFinishedPermission]

    @functools.cache
    def _user_answer(self):
        answer, _ = models.UserAnswer.objects.get_or_create(user=self.request.user)
        return answer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user_answer"] = self._user_answer()
        context["question"] = get_object_or_404(models.NeoQuestion, pk=self.kwargs["neo_pk"])
        return context

    def list(self, request, *args, **kwargs):
        return Response(self._user_answer().neo_answer)

    @action(methods=["GET"], detail=False, url_path="neo-score")
    def user_neo_score(self, request, *args, **kwargs):
        return Response(user_neo_score(request.user))

    @action(methods=["GET"], detail=False, url_path="get-neo-answer")
    def get_neo_answer_by_question(self, request, *args, **kwargs):
        question_id: str = self.kwargs["neo_pk"]
        user_answer = self._user_answer()
        answer = user_answer.answer["neo"]["answers"].get(question_id, None)

        if not answer:
            return Response({"detail": "به این سوال پاسخ داده نشده است!"}, status=status.HTTP_200_OK)

        return Response(answer, status=status.HTTP_200_OK)


class NeoFinishedUsersCount(APIView):
    permission_classes = [IsSysgod | IsUser]

    def get(self, request):
        neo_users = models.UserAnswer.objects.filter(answer__neo__status="finished")
        neo_users_list = neo_users.values_list("user", flat=True)
        question_count = models.NeoQuestion.objects.all().count()

        users = []
        for user_id in neo_users_list:
            user = get_user_model().objects.filter(id=user_id).first()
            if not user:
                continue
            users.append({"full_name": user.full_name, "national_id": user.user_info.get("national_id", None)})

        users_count = neo_users.count()
        return Response(
            {
                "users_count": users_count,
                "users_list": users if request.user.role == 0 else None,
                "neo_question_count": question_count,
            },
            status=status.HTTP_200_OK,
        )
