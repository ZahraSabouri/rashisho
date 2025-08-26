import datetime

import pandas as pd
from django.core.management.base import BaseCommand

from apps.account.models import User
from apps.project.models import Project, Team, TeamRequest


def convert_to_persian(number):
    english_digits = "0123456789"
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"

    translation_table = str.maketrans(english_digits, persian_digits)

    return str(number).translate(translation_table)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="The path to the team.xlsx file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file_path"]

        try:
            data = pd.read_excel(
                file_path,
                dtype={
                    "کد ملی نماینده": str,
                    "کد ملی عضو دوم": str,
                    "کد ملی عضو سوم": str,
                    "کد ملی عضو چهارم": str,
                    "کد ملی عضو پنجم": str,
                    "کد ملی عضو ششم": str,
                    "نام پروژه": str,
                    "نام تیم": str,
                    "تاریخ ثبت": str,
                    "شماره موبایل نماینده تیم": str,
                },
            )
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("Team file not found!"))
            return

        not_founded1, not_founded2, not_founded3, not_founded4, not_founded5, not_founded6 = [], [], [], [], [], []
        teams = []
        not_founded_project = []
        data["شماره موبایل نماینده تیم"] = data["شماره موبایل نماینده تیم"].apply(lambda x: str(x).zfill(11))

        for index, row in data.iterrows():
            team_member_count = 1
            phone1 = str(row["شماره موبایل نماینده تیم"])
            national_id1 = str(row["کد ملی نماینده"])
            national_id2 = str(row["کد ملی عضو دوم"])
            national_id3 = str(row["کد ملی عضو سوم"])
            national_id4 = str(row["کد ملی عضو چهارم"])
            national_id5 = str(row["کد ملی عضو پنجم"])
            national_id6 = str(row["کد ملی عضو ششم"])
            team_title = str(row["نام تیم"])
            project_title = str(row["نام پروژه"])

            # convert jalali to gregorian
            # if str(row["تاریخ ثبت"]) == "nan":
            #     g_creation_time = None
            # else:
            #     creation_time = str(row["تاریخ ثبت"]).split()[0].split("/")
            #     p_creation_time = jdatetime.date(int(creation_time[0]), int(creation_time[1]), int(creation_time[2]))
            #     g_creation_time = p_creation_time.togregorian()

            project = Project.objects.filter(title=project_title).first()

            if not project:
                not_founded_project.append(project_title)

            user1 = User.objects.filter(user_info__national_id=national_id1).first()
            if not user1:
                user1 = User.objects.filter(username=phone1).first()
                if not user1:
                    user1 = User.objects.filter(user_info__national_id=convert_to_persian(national_id1)).first()
                if not user1:
                    not_founded1.append(national_id1)
                    continue

            team = Team.objects.create(title=team_title, project=project, create_date=datetime.date.today())

            TeamRequest.objects.create(user=user1, team=team, status="A", user_role="C")

            user2 = User.objects.filter(user_info__national_id=national_id2).first()
            if not user2:
                user2 = User.objects.filter(user_info__national_id=convert_to_persian(national_id2)).first()
                if not user2:
                    not_founded2.append(national_id2)
            if user2:
                TeamRequest.objects.create(user=user2, team=team, status="A", user_role="M")
                team_member_count += 1

            user3 = User.objects.filter(user_info__national_id=national_id3).first()
            if not user3:
                user3 = User.objects.filter(user_info__national_id=convert_to_persian(national_id3)).first()
                if not user3:
                    not_founded3.append(national_id3)
            if user3:
                TeamRequest.objects.create(user=user3, team=team, status="A", user_role="M")
                team_member_count += 1

            user4 = User.objects.filter(user_info__national_id=national_id4).first()
            if not user4:
                user4 = User.objects.filter(user_info__national_id=convert_to_persian(national_id4)).first()
                if not user4:
                    not_founded4.append(national_id4)
            if user4:
                TeamRequest.objects.create(user=user4, team=team, status="A", user_role="M")
                team_member_count += 1

            user5 = User.objects.filter(user_info__national_id=national_id5).first()
            if not user5:
                user5 = User.objects.filter(user_info__national_id=convert_to_persian(national_id5)).first()
                if not user5:
                    not_founded5.append(national_id5)
            if user5:
                TeamRequest.objects.create(user=user5, team=team, status="A", user_role="M")
                team_member_count += 1

            user6 = User.objects.filter(user_info__national_id=national_id6).first()
            if not user6:
                user6 = User.objects.filter(user_info__national_id=convert_to_persian(national_id6)).first()
                if not user6:
                    not_founded6.append(national_id6)
            if user6:
                TeamRequest.objects.create(user=user6, team=team, status="A", user_role="M")
                team_member_count += 1

            team.count = team_member_count
            team.save()
            teams.append(team.title)

        print(f"not_founded_project_count: {len(not_founded_project)}")
        print(f"not_founded_project: {not_founded_project}")
        print("*********************************************")
        print(f"not_exists_user1_count: {len(not_founded1)}")
        print(f"not_exists_user1: {not_founded1}")
        print("*********************************************")
        print(f"not_exists_user2_count: {len(not_founded2)}")
        print(f"not_exists_user2: {not_founded2}")
        print("*********************************************")
        print(f"not_exists_user3_count: {len(not_founded3)}")
        print(f"not_exists_user3: {not_founded3}")
        print("*********************************************")
        print(f"not_exists_user4_count: {len(not_founded4)}")
        print(f"not_exists_user4: {not_founded4}")
        print("*********************************************")
        print(f"not_exists_user5_count: {len(not_founded5)}")
        print(f"not_exists_user5: {not_founded5}")
        print("*********************************************")
        print(f"not_exists_user6_count: {len(not_founded6)}")
        print(f"not_exists_user6: {not_founded6}")
        print("*********************************************")
        print(f"teams_count: {len(teams)}")
        print("*********************************************")

        print("Done successfully...")
