import io
from uuid import UUID

import xlsxwriter
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from apps.api.permissions import IsSysgod
from apps.exam import models, services


class BelbinReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("آزمون بلبین")
        worksheet.right_to_left()

        # Header Settings
        header_format = workbook.add_format(
            {
                "border": 1,
                "bold": True,
                "text_wrap": True,
                "valign": "vcenter",
                "align": "center",
                "bg_color": "#A5DEF2",
            }
        )

        # Rows Settings
        cell_format = workbook.add_format(
            {
                "font_size": 12,
                "border": 1,
                "text_wrap": True,
                "valign": "vcenter",
                "align": "center",
            }
        )

        worksheet.freeze_panes(2, 5)

        # Columns width
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:C", 20)
        worksheet.set_column("D:D", 20)

        # Rows Height
        worksheet.set_row(0, 35)
        for row in range(1, 10000):
            worksheet.set_row(row, 25)

        worksheet.merge_range("A1:A2", "ردیف", header_format)
        worksheet.merge_range("B1:B2", "نام و نام خانوادگی", header_format)
        worksheet.merge_range("C1:C2", "کد ملی", header_format)
        worksheet.merge_range("D1:D2", "شماره تماس", header_format)
        worksheet.merge_range("E1:E2", "جنسیت", header_format)

        # Generate questions in header
        last_column = 5
        belbin_questions = models.BelbinQuestion.objects.all().order_by("number")
        option_columns = {}

        for question in belbin_questions:
            options = models.BelbinAnswer.objects.filter(question=question).order_by("created_at")
            end_column = (last_column + options.count()) - 1
            worksheet.merge_range(0, last_column, 0, end_column, question.title, header_format)

            # Generate options under the question
            for col_num, option in enumerate(options, start=last_column):
                worksheet.write(1, col_num, option.answer, header_format)
                option_columns[option.id] = col_num

            last_column = end_column + 1

        # Generate data in rows
        row_num = 2
        user_answers = models.UserAnswer.objects.all().order_by("-created_at")
        for user_answer in user_answers:
            answers = user_answer.answer["belbin"]["answers"]
            exam_status = user_answer.answer["belbin"]["status"]
            user = user_answer.user
            if not answers or exam_status == "started":
                continue

            worksheet.write(f"A{row_num + 1}", row_num - 1, cell_format)
            worksheet.write(f"B{row_num + 1}", user.full_name, cell_format)
            worksheet.write(f"C{row_num + 1}", user.user_info.get("national_id", None), cell_format)
            worksheet.write(f"D{row_num + 1}", user.user_info.get("mobile_number", None), cell_format)
            worksheet.write(f"E{row_num + 1}", user.get_gender_display(), cell_format)

            for question_id, answer_dict in answers.items():
                for option_id, answer_value in answer_dict.items():
                    col_num = option_columns.get(UUID(option_id), None)
                    if col_num is not None:
                        worksheet.write(row_num, col_num, answer_value, cell_format)

            row_num += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(Belbin).xlsx"

        return response


class GeneralReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        general_exam_id = self.request.query_params["general"]
        option_columns = {}

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("آزمون عمومی")
        worksheet.right_to_left()

        # Header Settings
        header_format = workbook.add_format(
            {
                "border": 1,
                "bold": True,
                "text_wrap": True,
                "valign": "vcenter",
                "align": "center",
                "bg_color": "#A5DEF2",
            }
        )

        # Rows Settings
        cell_format = workbook.add_format(
            {
                "font_size": 12,
                "border": 1,
                "text_wrap": True,
                "valign": "vcenter",
                "align": "center",
            }
        )

        worksheet.freeze_panes(1, 5)

        # Columns Height
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:C", 20)
        worksheet.set_column("D:D", 20)
        worksheet.set_column(5, 40, 25)

        # Rows Height
        worksheet.set_row(0, 40)
        for row in range(1, 10000):
            worksheet.set_row(row, 25)

        # Generate Headers
        worksheet.write(0, 0, "ردیف", header_format)
        worksheet.write(0, 1, "نام و نام خانوادگی", header_format)
        worksheet.write(0, 2, "کد ملی", header_format)
        worksheet.write(0, 3, "شماره تماس", header_format)
        worksheet.write(0, 4, "جنسیت", header_format)

        general_questions = (
            models.GeneralQuestion.objects.filter(exam_id=str(general_exam_id))
            .order_by("number")
            .values_list("id", flat=True)
        )
        for col_num, header in enumerate(general_questions, start=5):
            question = get_object_or_404(models.GeneralQuestion, id=header)
            worksheet.write(0, col_num, f"سوال شماره {question.number}", header_format)
            option_columns[question.id] = col_num

        # Generate Rows
        row_num = 1
        user_answers = models.UserAnswer.objects.all()

        for user_answer in user_answers:
            user = user_answer.user
            answers = user_answer.answer["general"]["answers"].get(f"{general_exam_id}", None)
            if not answers:
                continue

            exam_status = answers["status"]
            if not exam_status:
                continue

            worksheet.write(f"A{row_num + 1}", row_num, cell_format)
            worksheet.write(f"B{row_num + 1}", user.full_name, cell_format)
            worksheet.write(f"C{row_num + 1}", user.user_info.get("national_id", None), cell_format)
            worksheet.write(f"D{row_num + 1}", user.user_info.get("mobile_number", None), cell_format)
            worksheet.write(f"E{row_num + 1}", user.get_gender_display(), cell_format)

            for key, value in answers.items():
                if key in ["status", "started", "finished"]:
                    continue

                general_option = models.GeneralQuestionOption.objects.filter(id=value).first()
                if not general_option:
                    continue

                col_num = option_columns.get(UUID(key), None)
                if col_num is not None:
                    worksheet.write(row_num, col_num, general_option.title, cell_format)

            row_num += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(General).xlsx"

        return response


class NeoReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("آزمون نئو")
        worksheet.right_to_left()
        option_columns = {}

        # Header Settings
        header_format = workbook.add_format(
            {
                "border": 1,
                "bold": True,
                "text_wrap": True,
                "valign": "vcenter",
                "align": "center",
                "bg_color": "#A5DEF2",
            }
        )

        # Rows Settings
        cell_format = workbook.add_format(
            {
                "font_size": 12,
                "border": 1,
                "text_wrap": True,
                "valign": "vcenter",
                "align": "center",
            }
        )

        worksheet.freeze_panes(1, 5)

        # Columns Height
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:C", 20)
        worksheet.set_column("D:D", 20)
        worksheet.set_column(5, 70, 20)

        # Rows Height
        worksheet.set_row(0, 40)
        for row in range(1, 20000):
            worksheet.set_row(row, 35)

        # Generate Headers
        worksheet.write(0, 0, "ردیف", header_format)
        worksheet.write(0, 1, "نام و نام خانوادگی", header_format)
        worksheet.write(0, 2, "کد ملی", header_format)
        worksheet.write(0, 3, "شماره تماس", header_format)
        worksheet.write(0, 4, "جنسیت", header_format)

        neo_questions = models.NeoQuestion.objects.all().order_by("number").values_list("id", flat=True)
        for col_num, header in enumerate(neo_questions, start=5):
            question = get_object_or_404(models.NeoQuestion, id=header)
            worksheet.write(0, col_num, f"({question.number}){question.title}", header_format)
            option_columns[question.id] = col_num

        neo_questions = {q.id: q for q in models.NeoQuestion.objects.all().order_by("number")}
        option_columns = {q.id: col_num + 5 for col_num, q in enumerate(neo_questions.values())}

        # Generate Rows
        row_num = 1
        user_answers = models.UserAnswer.objects.filter(~Q(answer__neo__answers={})).select_related("user")

        for user_answer in user_answers:
            answers = user_answer.answer["neo"]["answers"]
            exam_status = user_answer.answer["neo"]["status"]
            user = user_answer.user
            if exam_status == "started":
                continue

            worksheet.write(f"A{row_num + 1}", row_num, cell_format)
            worksheet.write(f"B{row_num + 1}", user.full_name, cell_format)
            worksheet.write(f"C{row_num + 1}", user.user_info.get("national_id", None), cell_format)
            worksheet.write(f"D{row_num + 1}", user.user_info.get("mobile_number", None), cell_format)
            worksheet.write(f"E{row_num + 1}", user.get_gender_display(), cell_format)

            for key, value in answers.items():
                neo_question = neo_questions.get(UUID(key))
                if neo_question:
                    option_value = services.get_neo_options_value(neo_question.options, value)
                    col_num = option_columns.get(UUID(key), None)
                    if col_num is not None:
                        worksheet.write(row_num, col_num, option_value, cell_format)

            row_num += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(Neo).xlsx"

        return response
