from django.db import migrations

def ensure_category_ref(apps, schema_editor):
    Tag = apps.get_model("project", "Tag")
    TagCategory = apps.get_model("project", "TagCategory")
    if Tag.objects.filter(category_ref__isnull=True).exists():
        misc, _ = TagCategory.objects.get_or_create(code="misc", defaults={"title": "Misc"})
        Tag.objects.filter(category_ref__isnull=True).update(category_ref=misc, category=misc.code)

class Migration(migrations.Migration):
    dependencies = [("project", "0049_backfill_tag_categories")]
    operations = [migrations.RunPython(ensure_category_ref, migrations.RunPython.noop)]
