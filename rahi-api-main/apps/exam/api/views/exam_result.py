import os

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status, views
from rest_framework.response import Response

from apps.api.permissions import IsSysgod, IsUser
from apps.exam.api.serializers import exam_result
from apps.exam.models import ExamResult, GeneralExam
from apps.exam.services import get_user_exam_status
from apps.project.api.serializers.file_serializer import ImportFileSerializer
from apps.resume.models import Resume


class ExamResultAPV(views.APIView):
    permission_classes = [IsSysgod | IsUser]
    serializer_class = exam_result.ExamResultSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsSysgod()]
        return super().get_permissions()

    def post(self, request, *args, **kwargs):
        exam_type = request.query_params["exam"]
        exam_id = request.query_params.get("exam_id", None)
        general_exam = GeneralExam.objects.filter(id=exam_id).first()
        if exam_id and not general_exam:
            return Response({"message": "آزمون با این آیدی وجود ندارد!"}, status=status.HTTP_400_BAD_REQUEST)

        file_serializer = ImportFileSerializer(data=request.data)
        if file_serializer.is_valid():
            file = file_serializer.validated_data["file"]
            file_name, _ = os.path.splitext(file.name)
            user = get_user_model().objects.filter(user_info__national_id=file_name).first()
            if not user:
                return Response({"message": "کاربری با این کدملی وجود ندارد!"}, status=status.HTTP_400_BAD_REQUEST)

            if not get_user_exam_status(user, exam_type, exam_id):
                return Response(
                    {"message": "این کاربر هنوز این آزمون را به انجام نرسانده است!"}, status=status.HTTP_400_BAD_REQUEST
                )

            result, created = ExamResult.objects.get_or_create(exam_id=exam_id, exam_type=exam_type, user=user)
            if result:
                result.delete()
                if exam_id:
                    ExamResult.objects.create(exam=general_exam, exam_type=exam_type, user=user, result_file=file)
                else:
                    ExamResult.objects.create(exam_type=exam_type, user=user, result_file=file)

            elif created:
                created.result_file = file

            return Response({"message": "عملیات با موفقیت انجام شد."}, status=status.HTTP_201_CREATED)

        return Response({"message": "خطایی رخ داده است!"}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, *args, **kwargs):
        """Each user wants to download his/her exam result"""

        exam_type = request.query_params.get("exam_type", None)
        exam_id = request.query_params.get("exam_id", None)
        resume_id = request.query_params.get("resume_id", None)
        user_id = self.request.user.id

        if resume_id:
            resume = get_object_or_404(Resume, id=resume_id)
            user_id = resume.user.id

        result = ExamResult.objects.filter(user_id=user_id, exam_type=exam_type)

        if exam_id:
            result = result.filter(exam_id=exam_id).first()
        else:
            result = result.first()

        if result:
            return Response({"message": result.result}, status=status.HTTP_200_OK)

        return Response({"message": "نتیجه آزمون وجود ندارد!"}, status=status.HTTP_400_BAD_REQUEST)
