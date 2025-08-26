import pandas as pd
from django.core.management.base import BaseCommand

from apps.project.models import Project


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="The path to the projects_telegram.xlsx file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file_path"]

        try:
            data = pd.read_excel(file_path)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("projects_telegram file not found!"))
            return

        not_founded_project = []
        for index, row in data.iterrows():
            project = row["project_id"]
            telegram = row["لینک گروه پروژه"]
            _project = Project.objects.filter(id=str(project)).first()
            if not project:
                not_founded_project.append({"ردیف": index, "پروژه": project})
                continue
            _project.telegram_id = telegram
            _project.save()

        print(f"not_founded_project: {not_founded_project}")
        print("Don successfully...")
