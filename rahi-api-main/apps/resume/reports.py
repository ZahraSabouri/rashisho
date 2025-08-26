import jdatetime
from django.http import HttpResponse
from rest_framework.views import APIView

from apps.account.models import User
from apps.api.permissions import IsSysgod
from apps.resume.models import Certificate, Connection, Education, Language, Project, Resume, Skill, WorkExperience


class ResumeReportAPV(APIView):
    permission_classes = [IsSysgod]

    def get(self, request):
        import io

        import xlsxwriter

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        worksheet_project = workbook.add_worksheet("اطلاعات رزومه")
        worksheet_project.right_to_left()
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
        worksheet_project.set_column("B:B", 20)
        worksheet_project.set_column("C:C", 18)
        worksheet_project.set_column("D:D", 18)
        worksheet_project.set_column("E:E", 10)
        worksheet_project.set_column("F:F", 10)
        worksheet_project.set_column("G:G", 15)
        worksheet_project.set_column("H:H", 10)
        worksheet_project.set_column("K:K", 50)
        worksheet_project.set_column("L:L", 50)
        worksheet_project.set_column("M:M", 30)
        worksheet_project.set_column("N:N", 30)
        worksheet_project.set_column("O:O", 40)
        worksheet_project.set_column("P:P", 40)
        worksheet_project.set_column("Q:Q", 40)

        # Rows Height
        for row in range(2, 1000):
            worksheet_project.set_row(row, 60)

        worksheet_project.freeze_panes(2, 2)
        worksheet_project.merge_range("A1:A2", "ردیف", header_format)
        worksheet_project.merge_range("B1:B2", "نام و نام خانوادگی", header_format)
        worksheet_project.merge_range("C1:C2", "کد ملی", header_format)
        worksheet_project.merge_range("D1:D2", "شماره همراه", header_format)
        worksheet_project.merge_range("E1:E2", "استان", header_format)
        worksheet_project.merge_range("F1:F2", "شهر", header_format)
        worksheet_project.merge_range("G1:G2", "تاریخ تولد", header_format)
        worksheet_project.merge_range("H1:H2", "جنسیت", header_format)
        worksheet_project.merge_range("I1:I2", "وضعیت تاهل", header_format)
        worksheet_project.merge_range("J1:J2", "وضعیت نظام وظیفه", header_format)
        worksheet_project.merge_range("K1:K2", "مقاطع تحصیلی", header_format)
        worksheet_project.merge_range("L1:L2", "سوابق شغلی", header_format)
        worksheet_project.merge_range("M1:M2", "مهارت ها", header_format)
        worksheet_project.merge_range("N1:N2", "زبان های خارجی", header_format)
        worksheet_project.merge_range("O1:O2", "راههای ارتباطی", header_format)
        worksheet_project.merge_range("P1:P2", "گواهی نامه ها", header_format)
        worksheet_project.merge_range("Q1:Q2", "پروژه", header_format)

        row_num = 1
        resumes = Resume.objects.all().values()

        for item in resumes:
            user = User.objects.get(id=item["user_id"])
            educations = Education.objects.filter(resume_id=item["id"])
            jobs = WorkExperience.objects.filter(resume_id=item["id"])
            skills = Skill.objects.filter(resume_id=item["id"])
            languages = Language.objects.filter(resume_id=item["id"])
            connections = Connection.objects.filter(resume_id=item["id"])
            certificates = Certificate.objects.filter(resume_id=item["id"])
            projects = Project.objects.filter(resume_id=item["id"])

            worksheet_project.write(f"A{row_num + 2}", row_num, cell_format)
            worksheet_project.write(f"B{row_num + 2}", user.full_name, cell_format)
            worksheet_project.write(f"C{row_num + 2}", user.user_info.get("national_id"), cell_format)
            worksheet_project.write(f"D{row_num + 2}", user.user_info.get("mobile_number"), cell_format)
            worksheet_project.write(f"E{row_num + 2}", user.city.province.title if user.city else None, cell_format)
            worksheet_project.write(f"F{row_num + 2}", user.city.title if user.city else None, cell_format)
            worksheet_project.write(
                f"G{row_num + 2}",
                jdatetime.datetime.fromgregorian(date=user.birth_date).strftime("%Y/%m/%d")
                if user.birth_date
                else None,
                cell_format,
            )
            worksheet_project.write(f"H{row_num + 2}", user.get_gender_display() if user.gender else None, cell_format)
            worksheet_project.write(
                f"I{row_num + 2}", user.get_marriage_status_display() if user.marriage_status else None, cell_format
            )
            worksheet_project.write(
                f"J{row_num + 2}", user.get_military_status_display() if user.military_status else None, cell_format
            )
            worksheet_project.write(
                f"K{row_num + 2}",
                " \n ".join(
                    [
                        f"{education.get_grade_display()} - {education.field.title} - {education.university}"
                        for education in educations
                    ]
                ),
                cell_format,
            )

            worksheet_project.write(
                f"L{row_num + 2}", " \n ".join([f"{job.job_title} - {job.company_name}" for job in jobs]), cell_format
            )

            worksheet_project.write(
                f"M{row_num + 2}",
                " \n ".join([f"{skill.skill_name} - {skill.get_level_display()}" for skill in skills]),
                cell_format,
            )

            worksheet_project.write(
                f"N{row_num + 2}",
                " \n ".join(
                    [f"{language.language_name.title} - {language.get_level_display()}" for language in languages]
                ),
                cell_format,
            )

            worksheet_project.write(
                f"O{row_num + 2}",
                " \n ".join([f"{connection.title} - {connection.link}" for connection in connections]),
                cell_format,
            )

            worksheet_project.write(
                f"P{row_num + 2}",
                " \n ".join(
                    [f"{certificate.certificate_title} - {certificate.institution}" for certificate in certificates]
                ),
                cell_format,
            )

            worksheet_project.write(
                f"Q{row_num + 2}",
                " \n ".join([f"{project.title} - {project.description}" for project in projects]),
                cell_format,
            )

            row_num += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=report(resume).xlsx"

        return response
