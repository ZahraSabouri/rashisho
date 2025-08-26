import io

import xlsxwriter
from django.http import HttpResponse
from rest_framework.views import APIView

from apps.api.permissions import IsSysgod
from apps.project import models
from apps.project.models import Team, TeamRequest
from apps.project.services import user_team
from apps.utils.utility import convert_to_jalali


class ProjectPriorityReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("الویت بندی پروژه")
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

        worksheet.freeze_panes(2, 3)

        # Columns width
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:C", 20)
        worksheet.set_column("D:D", 20)
        worksheet.set_column(5, 10, 30)

        # Rows Height
        worksheet.set_row(0, 35)
        for row in range(1, 10000):
            worksheet.set_row(row, 35)

        # Generate headers
        worksheet.merge_range("A1:A2", "ردیف", header_format)
        worksheet.merge_range("B1:B2", "نام و نام خانوادگی", header_format)
        worksheet.merge_range("C1:C2", "کد ملی", header_format)
        worksheet.merge_range("D1:D2", "شماره موبایل", header_format)
        worksheet.merge_range("E1:E2", "جنسیت", header_format)
        worksheet.merge_range("F1:F2", "الویت اول", header_format)
        worksheet.merge_range("G1:G2", "الویت دوم", header_format)
        worksheet.merge_range("H1:H2", "الویت سوم", header_format)
        worksheet.merge_range("I1:I2", "الویت چهارم", header_format)
        worksheet.merge_range("J1:J2", "الویت پنجم", header_format)
        worksheet.merge_range("K1:K2", "پروژه تخصیص داده شده", header_format)

        # Generate data in rows
        row_num = 2
        allocations = models.ProjectAllocation.objects.all()
        for allocation in allocations:
            priority = allocation.priority
            user = allocation.user

            worksheet.write(f"A{row_num + 1}", row_num - 1, cell_format)
            worksheet.write(f"B{row_num + 1}", user.full_name, cell_format)
            worksheet.write(f"C{row_num + 1}", user.user_info.get("national_id", None), cell_format)
            worksheet.write(f"D{row_num + 1}", user.user_info.get("mobile_number", None), cell_format)
            worksheet.write(f"E{row_num + 1}", user.get_gender_display(), cell_format)
            worksheet.write(f"K{row_num + 1}", allocation.project.title if allocation.project else None, cell_format)

            for col_num, (key, value) in enumerate(priority.items(), start=5):
                if not value or value == "nan":
                    break

                project = models.Project.objects.filter(id=value).first()
                if not project:
                    continue
                worksheet.write(row_num, col_num, project.title, cell_format)

            row_num += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(Project-Priority).xlsx"

        return response


class TeamReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("اطلاعات تیم ها")
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

        worksheet.freeze_panes(2, 0)

        # Columns Height
        worksheet.set_column("A:A", 25)
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:C", 20)
        worksheet.set_column("D:D", 20)
        worksheet.set_column("E:E", 20)
        worksheet.set_column("F:F", 25)
        worksheet.set_column("G:G", 80)

        # Rows Height
        worksheet.set_row(0, 35)
        for row in range(1, 3000):
            worksheet.set_row(row, 25)

        # Generate headers
        worksheet.merge_range("A1:A2", "نام تیم", header_format)
        worksheet.merge_range("B1:E1", "اعضای تیم", header_format)
        worksheet.merge_range("F1:F2", "نماینده", header_format)
        worksheet.merge_range("G1:G2", "نام پروژه", header_format)
        worksheet.write("B2", "کد ملی", header_format)
        worksheet.write("C2", "نام و نام خانوادگی", header_format)
        worksheet.write("D2", "شماره موبایل", header_format)
        worksheet.write("E2", "جنسیت", header_format)

        # Generate data in rows
        row_num = 2
        team_requests = models.TeamRequest.objects.filter(status="A").order_by("team", "id")
        current_team = None
        current_creator = None
        current_project = None
        start_row = row_num

        for team_request in team_requests:
            user = team_request.user
            team = team_request.team
            creator = TeamRequest.objects.filter(team=team, user_role="C").first().user
            project = Team.objects.filter(title=team).first().project

            team_member_count = models.TeamRequest.objects.filter(team=team, status="A").count()
            if team_member_count < 2:
                continue

            if current_team is None or team != current_team:
                if current_team is not None:
                    worksheet.merge_range(f"A{start_row + 1}:A{row_num}", current_team.title, cell_format)
                    worksheet.merge_range(f"F{start_row + 1}:F{row_num}", current_creator.full_name, cell_format)
                    worksheet.merge_range(f"G{start_row + 1}:G{row_num}", current_project.title, cell_format)
                current_team = team
                current_creator = creator
                current_project = project
                start_row = row_num

            worksheet.write(f"B{row_num + 1}", user.user_info.get("national_id", None), cell_format)
            worksheet.write(f"C{row_num + 1}", user.full_name, cell_format)
            worksheet.write(f"D{row_num + 1}", user.user_info.get("mobile_number", None), cell_format)
            worksheet.write(f"E{row_num + 1}", user.get_gender_display(), cell_format)

            row_num += 1

        if current_team is not None:
            worksheet.merge_range(f"A{start_row + 1}:A{row_num}", current_team.title, cell_format)
            worksheet.merge_range(f"F{start_row  + 1}:F{row_num}", current_creator.full_name, cell_format)
            worksheet.merge_range(f"G{start_row  + 1}:G{row_num}", current_project.title, cell_format)

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(Team).xlsx"

        return response


class FinalRepresentationReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("ارائه نهایی")
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

        # Columns Height
        worksheet.set_column("A:A", 25)
        worksheet.set_column("B:B", 25)
        worksheet.set_column("C:C", 25)
        worksheet.set_column("E:E", 25)
        worksheet.set_column("F:F", 100)

        # Rows Height
        worksheet.set_row(0, 35)
        for row in range(1, 3000):
            worksheet.set_row(row, 25)

        # Generate headers
        worksheet.write("A1:A2", "نام و نام خانوادگی", header_format)
        worksheet.write("B1:B2", "کد ملی", header_format)
        worksheet.write("C1:C2", "شماره تماس", header_format)
        worksheet.write("D1:D2", "جنسیت", header_format)
        worksheet.write("E1:E2", "نام تیم", header_format)
        worksheet.write("F1:F2", "پروژه", header_format)
        worksheet.write("G1:G2", "آدرس دانلود فایل ارائه نهایی", header_format)

        # Generate data in rows
        final_reps = models.UserScenarioTaskFile.objects.filter(derivatives__derivatives_type="F")
        row_num = 1
        for rep in final_reps:
            worksheet.write(f"A{row_num + 1}", rep.user.full_name, cell_format)
            worksheet.write(f"B{row_num + 1}", rep.user.user_info.get("national_id", None), cell_format)
            worksheet.write(f"C{row_num + 1}", rep.user.user_info.get("mobile_number", None), cell_format)
            worksheet.write(f"D{row_num + 1}", rep.user.get_gender_display(), cell_format)
            worksheet.write(f"E{row_num + 1}", user_team(rep.user), cell_format)
            worksheet.write(f"F{row_num + 1}", rep.derivatives.project.title, cell_format)
            worksheet.write(
                f"G{row_num + 1}",
                f"https://rahisho.online/api/v1/project/final-rep/file/{rep.user.id}",
                cell_format,
            )

            row_num += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(FinalRepresentation).xlsx"

        return response


class ScenarioReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("سناریو")
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

        # Columns Height
        worksheet.set_column("A:A", 25)
        worksheet.set_column("B:B", 25)
        worksheet.set_column("C:C", 25)
        worksheet.set_column("D:D", 90)
        worksheet.set_column("E:E", 90)

        # Rows Height
        worksheet.set_row(0, 35)
        for row in range(1, 3000):
            worksheet.set_row(row, 30)

        # Generate headers
        worksheet.write("A1:A2", "عنوان پروژه", header_format)
        worksheet.write("B1:B2", "عنوان سناریو", header_format)
        worksheet.write("C1:C2", "توضیحات سناریو", header_format)
        worksheet.write("D1:D2", "فایل اول", header_format)
        worksheet.write("E1:E2", "فایل دوم", header_format)

        worksheet.freeze_panes(1, 1)

        # Generate data in rows
        last_row = 2
        scenario_rows = {}
        projects = models.Project.objects.all().order_by("created_at")
        for project in projects:
            scenarios = models.Scenario.objects.filter(project=project).order_by("number")
            end_row = (last_row + scenarios.count()) - 1

            if not scenarios:
                continue
            if scenarios.count() > 1:
                worksheet.merge_range(f"A{last_row}:A{end_row}", project.title, cell_format)
            else:
                worksheet.write(f"A{last_row}", project.title, cell_format)

            # Generate scenario under the project
            for row_num, scenario in enumerate(scenarios, start=last_row):
                worksheet.write(f"A{row_num}", scenario.project.title, cell_format)
                worksheet.write(f"B{row_num}", scenario.title, cell_format)
                worksheet.write(f"C{row_num}", scenario.description, cell_format)
                worksheet.write(
                    f"D{row_num}",
                    f"https://rahishu.tadbirserver.ir/api/v1/project/scenario/{scenario.id}/files/?type=first",
                    cell_format,
                )
                worksheet.write(
                    f"E{row_num}",
                    f"https://rahishu.tadbirserver.ir/api/v1/project/scenario/{scenario.id}/files/?type=second",
                    cell_format,
                )
                scenario_rows[scenario.id] = row_num

            last_row = end_row + 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(Scenario).xlsx"

        return response


class TaskReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("کارویژه")
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

        # Columns Height
        worksheet.set_column("A:A", 25)
        worksheet.set_column("B:B", 25)
        worksheet.set_column("C:C", 25)
        worksheet.set_column("D:D", 90)
        worksheet.set_column("E:E", 25)
        worksheet.set_column("F:F", 30)
        worksheet.set_column("G:G", 80)
        worksheet.set_column("H:H", 35)
        worksheet.set_column("I:I", 35)
        worksheet.set_column("J:J", 80)

        # Rows Height
        worksheet.set_row(0, 35)
        for row in range(1, 3000):
            worksheet.set_row(row, 30)

        # Generate headers
        worksheet.write("A1:A2", "نام و نام خانوادگی", header_format)
        worksheet.write("B1:B2", "شماره تماس", header_format)
        worksheet.write("C1:C2", "کد ملی", header_format)
        worksheet.write("D1:D2", "عنوان پروژه", header_format)
        worksheet.write("E1:E2", "عنوان کارویژه", header_format)
        worksheet.write("F1:F2", "نام تیم", header_format)
        worksheet.write("G1:G2", "فایل ارسالی از سمت کاربر", header_format)
        worksheet.write("H1:H2", "تاریخ ارسال", header_format)
        worksheet.write("I1:I2", "تاریخ ویرایش", header_format)
        worksheet.write("J1:J2", "فایل اول", header_format)

        worksheet.freeze_panes(1, 1)

        # Generate data in rows
        row_num = 2
        for item in models.UserScenarioTaskFile.objects.all():
            p_created_at, create_time = convert_to_jalali(item.created_at)
            p_updated_at, update_time = convert_to_jalali(item.updated_at)
            if not item.task:
                continue
            _task = models.Task.objects.filter(id=item.task.id).first()
            if not _task:
                continue
            _team_request = models.TeamRequest.objects.filter(user=item.user).first()
            worksheet.write(f"A{row_num}", item.user.full_name, cell_format)
            worksheet.write(f"B{row_num}", item.user.mobile_number, cell_format)
            worksheet.write(f"C{row_num}", item.user.user_info.get("national_id", None), cell_format)
            worksheet.write(f"D{row_num}", _task.project.title, cell_format)
            worksheet.write(
                f"E{row_num}",
                _task.title,
                cell_format,
            )
            worksheet.write(f"F{row_num}", _team_request.team.title if _team_request else None, cell_format)
            worksheet.write(
                f"G{row_num}",
                f"https://rahisho.online{item.file.url}",
                cell_format,
            )
            worksheet.write(f"H{row_num}", f"{p_created_at}  {create_time}", cell_format)
            worksheet.write(f"I{row_num}", f"{p_updated_at}  {update_time}", cell_format)
            worksheet.write(
                f"J{row_num}",
                f"https://rahisho.online{item.task.first_file.url}",
                cell_format,
            )

            row_num += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(Task).xlsx"

        return response


class AllocatedProjectReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("پروژه های تخصیص یافته")
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
        worksheet.set_column("B:B", 20)
        worksheet.set_column("C:C", 40)
        worksheet.set_column("D:D", 30)
        worksheet.set_column("E:E", 30)

        # Rows Height
        worksheet.set_row(0, 35)
        for row in range(1, 10000):
            worksheet.set_row(row, 25)

        # Generate Headers
        worksheet.write(0, 0, "ردیف", header_format)
        worksheet.write(0, 1, "کد پروژه", header_format)
        worksheet.write(0, 2, "عنوان پروژه", header_format)
        worksheet.write(0, 3, "راهبر پروژه", header_format)
        worksheet.write(0, 4, "شرکت تعریف کننده پروژه", header_format)

        # Generate Rows
        row_num = 1
        allocations = (
            models.ProjectAllocation.objects.filter(project__isnull=False).order_by("project_id").distinct("project")
        )

        for allocation in allocations:
            worksheet.write(f"A{row_num + 1}", row_num, cell_format)
            worksheet.write(f"B{row_num + 1}", allocation.project.code, cell_format)
            worksheet.write(f"C{row_num + 1}", allocation.project.title, cell_format)
            worksheet.write(f"D{row_num + 1}", allocation.project.leader, cell_format)
            worksheet.write(f"E{row_num + 1}", allocation.project.company, cell_format)

            row_num += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(AllocatedProject).xlsx"

        return response
