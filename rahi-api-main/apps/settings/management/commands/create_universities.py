import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.settings.models import University
from conf.settings import BASE_DIR


class Command(BaseCommand):
    @transaction.atomic()
    def handle(self, *args, **options):
        try:
            excel_content = pd.read_excel(BASE_DIR / "loaddata" / "universities.xlsx")
            excel_content = excel_content.values.tolist()

            universities = []
            for item in excel_content:
                if not University.objects.filter(title=item[0]).exists():
                    universities.append(University(title=item[0]))
            University.objects.bulk_create(universities)

            print("University successfully add to database")

        except Exception as e:
            print(str(e))
