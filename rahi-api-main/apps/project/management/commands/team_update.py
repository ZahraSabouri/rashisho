import pandas as pd
from django.core.management.base import BaseCommand

from apps.account.models import User
from apps.project.models import Team, TeamRequest, UserScenarioTaskFile


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="The path to the team_changes.xlsx file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file_path"]

        try:
            data = pd.read_excel(file_path, dtype={"کد ملی شرکت کننده": str})
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("team_update file not found!"))
            return

        user_list = []
        team_list = []

        for index, row in data.iterrows():
            operation = row["عملیات"]
            user = str(row["کد ملی شرکت کننده"])
            team_name = row["نام تیم"]

            _user = User.objects.filter(user_info__national_id=user).first()
            if not _user:
                user_list.append(user)
                continue
            _team = Team.objects.filter(title=team_name).first()

            if operation == "حذف از تیم":
                team_request = TeamRequest.objects.filter(user__user_info__national_id=user, team=_team).first()
                if not team_request:
                    team_list.append(user)
                    continue
                team_request.delete()

            if operation == "اضافه به تیم":
                if user == "5260462629":
                    team_request = TeamRequest.objects.filter(user=_user, status="A").first()
                    if team_request:
                        team_request.team = _team
                        team_request.user_role = "C"
                        team_request.save()

                    user_task_file = UserScenarioTaskFile.objects.filter(
                        user__user_info__national_id="1940709857"
                    ).first()
                    if user_task_file:
                        user_task_file.user = _user
                        user_task_file.save()

                else:
                    team_request = TeamRequest.objects.filter(user=_user, status="A").first()
                    if team_request:
                        team_request.team = _team
                        team_request.user_role = "M"
                        team_request.save()
                    else:
                        TeamRequest.objects.create(team=_team, user=_user, user_role="M", status="A")

        print(f"not_founded_user: {user_list}")
        print(f"not_founded_team: {team_list}")
