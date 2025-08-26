import pandas as pd
from django.core.management.base import BaseCommand

from apps.account.models import User
from apps.project.models import Project, ProjectAllocation


def convert_to_persian(number):
    english_digits = "0123456789"
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"

    translation_table = str.maketrans(english_digits, persian_digits)

    return str(number).translate(translation_table)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="The path to the allocation.xlsx file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file_path"]

        try:
            data = pd.read_excel(file_path, dtype={"کد ملی": str})
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("project_allocation file not found!"))
            return

        data = data.dropna(subset=["پروژه تخصیص داده شده"])

        not_exists_user = []
        for index, row in data.iterrows():
            national_id = row["کد ملی"]
            _user = User.objects.filter(user_info__national_id=str(national_id)).first()
            if not _user:
                persian_ni = convert_to_persian(str(row["کد ملی"]))
                _user = User.objects.filter(user_info__national_id=persian_ni).first()
                if not _user:
                    not_exists_user.append(national_id)
                    continue

            allocation = ProjectAllocation.objects.filter(user=_user).first()
            if not allocation:
                allocation = ProjectAllocation.objects.create(user=_user)

            project = Project.objects.filter(title=str(row["پروژه تخصیص داده شده"])).first()

            allocation.project = project
            allocation.save()

        print(f"not_exists_user_count: {len(not_exists_user)}")
        print(f"not_exists_user: {not_exists_user}")
        print("Don successfully...")
