import json

from django.core.management import BaseCommand

from apps.account.models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="The path to the user_info.json file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file_path"]

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("فایل یافت نشد."))
            print("TEST")
        no_mobile_users = User.objects.filter(user_info__mobile_number__isnull=True)

        for user_info in data:
            for key, value in user_info.items():
                if value == "true":
                    user_info[key] = True
                if value == "false":
                    user_info[key] = False

        for user in no_mobile_users:
            for user_info in data:
                if user_info["mobile_number"] == user.username:
                    user.user_info = user_info
                    user.save()

        print(len(no_mobile_users))
        print("Don Successfully")
