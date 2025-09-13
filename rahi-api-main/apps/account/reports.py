import io
from collections import defaultdict

import xlsxwriter
from django.http import HttpResponse
from rest_framework.views import APIView

from apps.account.models import User
from apps.api.permissions import IsSysgod
from apps.api.schema import TaggedAutoSchema
from apps.manager.permissions import IsSuperUser
from apps.project.models import ProjectAttractiveness


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


class UsersProjectAttractionsReportAPV(APIView):
    schema = TaggedAutoSchema(tags=["User"])
    permission_classes = [IsSuperUser]

    def get(self, request):
        # Build rows: national_id -> [project_code, ...]
        rows = defaultdict(list)

        qs = (
            ProjectAttractiveness.objects
            .select_related("user", "project")
            .order_by("user_id", "-created_at")
        )
        for pa in qs:
            nid = (pa.user.user_info or {}).get("national_id")
            if not nid:
                continue
            code = (pa.project.code or "").strip() if pa.project else ""
            if code:
                rows[nid].append(code)

        # Determine widest row to size columns
        max_projects = max((len(v) for v in rows.values()), default=0)

        # Write Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        ws = workbook.add_worksheet("پروژه‌های جذاب")
        ws.right_to_left()

        header_fmt = workbook.add_format(
            {"border": 1, "bold": True, "valign": "vcenter", "align": "center", "bg_color": "#A5DEF2"}
        )
        cell_fmt = workbook.add_format({"border": 1, "valign": "vcenter"})

        # Column widths
        ws.set_column(0, 0, 22)  # National ID
        ws.set_column(1, max(1, max_projects), 20)

        # Headers
        ws.write(0, 0, "کد ملی", header_fmt)
        for i in range(max_projects):
            ws.write(0, i + 1, f"پروژه {i + 1}", header_fmt)

        # Rows
        row_idx = 1
        for nid, codes in rows.items():
            ws.write(row_idx, 0, nid, cell_fmt)
            for i, code in enumerate(codes):
                ws.write(row_idx, i + 1, code, cell_fmt)
            row_idx += 1

        workbook.close()
        output.seek(0)

        resp = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = "attachment; filename=report(Users-Project-Attractions).xlsx"
        return resp