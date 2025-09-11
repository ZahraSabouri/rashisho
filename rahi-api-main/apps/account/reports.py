import io

import xlsxwriter
from django.http import HttpResponse
from rest_framework.views import APIView

from apps.account.models import User
from apps.api.permissions import IsSysgod
from apps.api.schema import TaggedAutoSchema
from apps.manager.permissions import IsSuperUser


class UsersReportAPV(APIView):
    schema = TaggedAutoSchema(tags=["User"])
    permission_classes = [IsSuperUser]

    def get(self, request):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("اطلاعات کاربران")
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

        worksheet.freeze_panes(1, 0)

        # Columns width
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:C", 25)
        worksheet.set_column("D:D", 25)

        # Rows Height
        worksheet.set_row(0, 35)
        for row in range(1, 20000):
            worksheet.set_row(row, 25)

        # Generate Headers
        worksheet.write(0, 0, "ردیف", header_format)
        worksheet.write(0, 1, "نام و نام خانوادگی", header_format)
        worksheet.write(0, 2, "شماره موبایل", header_format)
        worksheet.write(0, 3, "کد ملی", header_format)
        worksheet.write(0, 4, "جنسیت", header_format)

        # Generate Rows
        row_num = 1
        users = User.objects.all()

        for user in users:
            worksheet.write(f"A{row_num + 1}", row_num, cell_format)
            worksheet.write(f"B{row_num + 1}", user.full_name, cell_format)
            worksheet.write(f"C{row_num + 1}", user.user_info.get("mobile_number"), cell_format)
            worksheet.write(f"D{row_num + 1}", user.user_info.get("national_id"), cell_format)
            worksheet.write(f"E{row_num + 1}", user.get_gender_display(), cell_format)

            row_num += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(Users).xlsx"

        return response
