import pandas as pd
from django.core.management import BaseCommand

from apps.account.models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="The path to the persian_national_id.json file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file_path"]

        try:
            data = pd.read_excel(file_path, dtype={"شماره موبایل": str, "کد ملی سایت": str, "کد ملی انگلیسی": str})

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("File not found!"))

        data["شماره موبایل"] = data["شماره موبایل"].apply(lambda x: str(x).zfill(11))

        not_founded_user = []
        for index, row in data.iterrows():
            username = row["شماره موبایل"]
            p_national_id = str(row["کد ملی سایت"])
            e_national_id = str(row["کد ملی انگلیسی"])
            _user = User.objects.filter(username=username).first()
            if not _user:
                _user = User.objects.filter(user_info__national_id=p_national_id).first()
                if not _user:
                    not_founded_user.append(username)
                    continue

            _user.user_info["national_id"] = e_national_id
            _user.save()

        print(f"not_founded_user: {not_founded_user}")
        print(f"not_founded_user_count: {len(not_founded_user)}")
        print("Done Successfully")
