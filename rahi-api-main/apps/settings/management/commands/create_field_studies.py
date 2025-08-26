import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.settings.models import StudyField
from conf.settings import BASE_DIR


class Command(BaseCommand):
    @transaction.atomic()
    def handle(self, *args, **options):
        try:
            excel_content = pd.read_excel(BASE_DIR / "loaddata" / "field-studies.xlsx")
            excel_content = excel_content.values.tolist()

            
            universities = []
            for item in excel_content:
                if not StudyField.objects.filter(title=item[1]).exists():
                    universities.append(StudyField(title=item[1]))
            StudyField.objects.bulk_create(universities)

            print("Study Fields successfully add to database")

        except Exception as e:
            print(str(e))
