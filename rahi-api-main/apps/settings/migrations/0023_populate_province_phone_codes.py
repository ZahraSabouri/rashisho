from django.db import migrations

PROVINCE_PHONE_CODES = {
    "تهران": "21",
    "اصفهان": "31",
    "مشهد": "51",
    "شیراز": "71",
    "تبریز": "41",
    "کرج": "26",
    "قم": "25",
    "اهواز": "61",
    "کرمانشاه": "83",
    "ارومیه": "44",
    "رشت": "13",
    "کرمان": "34",
    "همدان": "81",
    "یزد": "35",
    "اردبیل": "45",
    "بندرعباس": "76",
    "زنجان": "24",
    "سنندج": "87",
    "قزوین": "28",
    "ساری": "11",
    "بجنورد": "58",
    "خرم‌آباد": "66",
    "ایلام": "84",
    "بوشهر": "77",
    "بیرجند": "56",
    "شهرکرد": "38",
    "یاسوج": "74",
    "گرگان": "17",
    "زاهدان": "54",
    "سمنان": "23",
}

def populate_phone_codes(apps, schema_editor):
    Province = apps.get_model("settings", "Province")

    # Be robust to either `name` or `title` as the label field.
    label_field = None
    for candidate in ("name", "title"):
        try:
            Province._meta.get_field(candidate)
            label_field = candidate
            break
        except Exception:
            continue
    if not label_field:
        # Can't safely map without a readable label field
        return

    # Update only when mapping ey matches province label exactly.
    # Keep it conservative to avoid accidental mismatches.
    to_update = []
    for province in Province.objects.all():
        label = getattr(province, label_field, None)
        if not label:
            continue
        code = PROVINCE_PHONE_CODES.get(label)
        if code and province.phone_code != code:
            province.phone_code = code
            to_update.append(province)

    if to_update:
        Province.objects.bulk_update(to_update, ["phone_code"])

class Migration(migrations.Migration):

    dependencies = [
        ("settings", "0022_province_phone_code"),
    ]

    operations = [
        migrations.RunPython(populate_phone_codes, migrations.RunPython.noop),
    ]
