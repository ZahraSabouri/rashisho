import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.account.models import User
from apps.exam.models import ExamResult


def convert_data_to_national_id(statement: str):
    return statement.split()[-1].split(".")[0]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="The path to the exam_result.xlsx file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file_path"]

        try:
            data = pd.read_excel(file_path)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("project_allocation file not found!"))
            return

        e_type = {"belbin": "B", "neo": "N"}

        national_ids = data["کد ملی"].apply(lambda x: convert_data_to_national_id(str(x)))

        users = User.objects.filter(user_info__national_id__in=national_ids)
        user_dict = {user.user_info["national_id"]: user for user in users}

        results_to_create = []
        not_exists_user = []

        for index, row in data.iterrows():
            national_id = convert_data_to_national_id(str(row["کد ملی"]))
            exam_type = row["نوع آزمون"]
            _user = user_dict.get(national_id)

            if not _user:
                not_exists_user.append(national_id)
                continue

            address = f"https://rahisho.online/{exam_type}/pdf/{national_id}.pdf"
            exam_type_code = e_type.get(str(exam_type))
            results_to_create.append(ExamResult(user=_user, exam_type=exam_type_code, result=address))
        if results_to_create:
            with transaction.atomic():
                ExamResult.objects.bulk_create(results_to_create)

        print(f"not_exists_user_count: {len(not_exists_user)}")
        print(f"not_exists_user: {not_exists_user}")
        print("Don successfully...")
