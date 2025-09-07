from django.http import HttpResponse
from rest_framework.views import APIView

from apps.api.permissions import IsSysgod
from apps.community.models import Community

from apps.api.schema import TaggedAutoSchema

class CommunityMembersReportAPV(APIView):
    schema = TaggedAutoSchema(tags=["Community"])
    permission_classes = [IsSysgod]

    def get(self, request):
        import io

        import xlsxwriter

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        worksheet = workbook.add_worksheet("کاربران انجمن")
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

        # Columns width
        worksheet.set_column("A:A", 30)
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:C", 25)
        worksheet.set_column("D:D", 25)
        worksheet.set_column("F:F", 25)
        worksheet.set_column("G:G", 25)
        worksheet.set_column("H:H", 25)

        # Rows Height
        worksheet.set_row(0, 40)
        for row in range(1, 10000):
            worksheet.set_row(row, 30)

        worksheet.freeze_panes(2, 1)

        worksheet.merge_range("A1:A2", "عنوان انجمن", header_format)

        worksheet.merge_range("B1:E1", "مدیر انجمن", header_format)
        worksheet.write("B2", "نام و نام خانوادگی", header_format)
        worksheet.write("C2", "کد ملی", header_format)
        worksheet.write("D2", "شماره تماس", header_format)
        worksheet.write("E2", "جنسیت", header_format)

        worksheet.merge_range("F1:I1", "اطلاعات اعضای انجمن", header_format)
        worksheet.write("F2", "نام و نام خانوادگی", header_format)
        worksheet.write("G2", "کد ملی", header_format)
        worksheet.write("H2", "شماره تماس", header_format)
        worksheet.write("I2", "جنسیت", header_format)

        # Generate data in rows
        last_row = 3
        member_rows = {}
        communities = Community.objects.all()
        for community in communities:
            members = community.users.all()
            end_row = (last_row + members.count()) - 1

            if not members:
                continue

            if members.count() > 1:
                worksheet.merge_range(f"A{last_row}:A{end_row}", community.title, cell_format)
                worksheet.merge_range(f"B{last_row}:B{end_row}", community.manager.full_name, cell_format)
                worksheet.merge_range(
                    f"C{last_row}:C{end_row}", community.manager.user_info["national_id"], cell_format
                )
                worksheet.merge_range(
                    f"D{last_row}:D{end_row}", community.manager.user_info["mobile_number"], cell_format
                )
                worksheet.merge_range(f"E{last_row}:E{end_row}", community.manager.get_gender_display(), cell_format)
            else:
                worksheet.write(f"A{last_row}", community.title, cell_format)
                worksheet.write(f"B{last_row}", community.manager.full_name, cell_format)
                worksheet.write(f"C{last_row}", community.manager.user_info["national_id"], cell_format)
                worksheet.write(f"D{last_row}", community.manager.user_info["mobile_number"], cell_format)
                worksheet.write(f"E{last_row}", community.manager.get_gender_display(), cell_format)

            # Generate users under the community
            for row_num, user in enumerate(members, start=last_row):
                worksheet.write(f"F{row_num}", user.full_name, cell_format)
                worksheet.write(f"G{row_num}", user.user_info["national_id"], cell_format)
                worksheet.write(f"H{row_num}", user.user_info["mobile_number"], cell_format)
                worksheet.write(f"I{row_num}", user.get_gender_display(), cell_format)
                member_rows[user.id] = row_num

            last_row = end_row + 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(CommunityMembers).xlsx"

        return response
