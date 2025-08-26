import pandas as pd
from django.core.management.base import BaseCommand

from apps.account.models import User
from apps.project.models import Project, ProjectAllocation, Team, TeamRequest


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="The path to the team.xlsx file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file_path"]

        try:
            data = pd.read_excel(
                file_path,
                dtype={
                    "کد ملی عضو جدید": str,
                    "نام تیم": str,
                    "پروژه": str,
                },
            )
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("Team file not found!"))
            return

        not_founded1, not_founded2 = [], []
        # data["شماره موبایل نماینده تیم"] = data["شماره موبایل نماینده تیم"].apply(lambda x: str(x).zfill(11))

        for index, row in data.iterrows():
            member_national_id = str(row["کد ملی عضو جدید"])
            team_title = str(row["نام تیم"])
            project_title = str(row["پروژه"])
            user = User.objects.filter(user_info__national_id=member_national_id).first()
            if not user:
                not_founded1.append(member_national_id)
                continue
            project = Project.objects.filter(title=project_title).first()
            if not project:
                not_founded2.append(project_title)
                continue

            if member_national_id in ["1850351511", "0925106704"]:
                ProjectAllocation.objects.create(user=user, project=project)

            team = Team.objects.filter(title=team_title).first()
            team_request = TeamRequest.objects.filter(user=user, status="A").first()
            if team_request:
                team_request.team = team
                team_request.user_role = "M"
                team_request.save()
            else:
                TeamRequest.objects.create(team=team, user=user, status="A", user_role="M")

        print(f"not_founded_user_count: {len(not_founded1)}")
        print(f"not_founded_user: {not_founded1}")
        print("*********************************************")
        print(f"not_founded_project_count: {len(not_founded2)}")
        print(f"not_founded_project: {not_founded2}")
        print("*********************************************")
        print("Done successfully...")
