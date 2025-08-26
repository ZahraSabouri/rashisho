import functools

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.api.permissions import IsSysgod, IsUser, ResumeFinishedPermission
from apps.exam import models
from apps.exam.api.serializers import belbin as serializers
from apps.exam.services import check_user_next_question


class BelbinQuestionVS(ModelViewSet):
    serializer_class = serializers.BelbinQuestionSerializer
    queryset = models.BelbinQuestion.objects.all().prefetch_related("belbin_answer_question").order_by("number")
    permission_classes = [ResumeFinishedPermission]

    def get_permissions(self):
        if self.action in ["create", "destroy", "partial_update", "update"]:
            return [IsSysgod()]
        return super().get_permissions()

    @action(methods=["get"], detail=False, permission_classes=[IsAuthenticated])
    def belbin_user_next_question(self, request, *args, **kwargs):
        """Here we check the user answers and return him the next question."""
        question = check_user_next_question(user=self.request.user, exam="belbin", model=models.BelbinQuestion)
        serializer = self.serializer_class(question)
        return Response(serializer.data)


class BelbinMultiCreate(CreateModelMixin, GenericViewSet):
    serializer_class = serializers.BelbinMultiCreateSerializer
    queryset = models.BelbinQuestion.objects.all()
    permission_classes = [IsSysgod]

    @action(methods=["post"], detail=False)
    def update_question_options(self, request, *args, **kwargs):
        serializer = serializers.BelbinMultiUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BelbinUserAnswer(GenericViewSet, CreateModelMixin, ListModelMixin):
    serializer_class = serializers.BelbinMultipleUserSerializer
    permission_classes = [ResumeFinishedPermission]

    @functools.cache
    def _user_answer(self):
        answer, _ = models.UserAnswer.objects.get_or_create(user=self.request.user)
        return answer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user_answer"] = self._user_answer()
        return context

    def list(self, request, *args, **kwargs):
        return Response(self._user_answer().belbin_answer)


class BelbinFinishedUsersCount(APIView):
    permission_classes = [IsSysgod | IsUser]

    def get(self, request):
        belbin_users = models.UserAnswer.objects.filter(answer__belbin__status="finished")
        belbin_users_list = belbin_users.values_list("user", flat=True)
        question_count = models.BelbinQuestion.objects.all().count()

        users = []
        for user_id in belbin_users_list:
            user = get_user_model().objects.filter(id=user_id).first()
            if not user:
                continue
            users.append({"full_name": user.full_name, "national_id": user.user_info.get("national_id", None)})

        users_count = belbin_users.count()
        return Response(
            {
                "users_count": users_count,
                "users_list": users if request.user.role == 0 else None,
                "belbin_question_count": question_count,
            },
            status=status.HTTP_200_OK,
        )


class RemoveUserExamAnswer(APIView):
    permission_classes = [IsUser | IsSysgod]

    def get(self, request, *args, **kwargs):
        """Here we remove the exam answer for a user"""

        exam = self.request.query_params.get("exam", None)
        if not exam:
            return Response({"نوع آزمون را ارسال کنید!"}, status=status.HTTP_400_BAD_REQUEST)

        user_answer = models.UserAnswer.objects.filter(user=self.request.user).first()
        if not user_answer:
            return Response({"شما هیچ پاسخی برای این آزمون ثبت نکرده اید!"}, status=status.HTTP_400_BAD_REQUEST)

        answers = user_answer.answer.get(f"{exam}").get("answers")
        if not answers:
            return Response({"شما هیچ پاسخی برای این آزمون ثبت نکرده اید!"}, status=status.HTTP_400_BAD_REQUEST)

        user_answer.answer[f"{exam}"]["answers"] = {}
        user_answer.answer[f"{exam}"]["status"] = "started"
        user_answer.save()
        return Response({"عملیات با موفقیت انجام شد."}, status=status.HTTP_200_OK)
