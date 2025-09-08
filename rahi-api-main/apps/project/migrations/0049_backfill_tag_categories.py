from django.db import migrations
from django.utils.text import slugify

def forwards(apps, schema_editor):
    Tag = apps.get_model('project', 'Tag')
    TagCategory = apps.get_model('project', 'TagCategory')

    # 0) Ensure a KEYWORD default category exists
    default_title = 'کلیدواژه'
    default_cat, _ = TagCategory.objects.get_or_create(code='KEYWORD', defaults={'title': default_title})

    # 1) Normalize empty/NULL Tag.category to KEYWORD for safety
    Tag.objects.filter(category__isnull=True).update(category='KEYWORD')
    Tag.objects.filter(category='').update(category='KEYWORD')

    # 2) Create TagCategory rows for every distinct Tag.category
    codes = (
        Tag.objects.exclude(category__isnull=True)
                   .exclude(category='')
                   .values_list('category', flat=True)
                   .distinct()
    )
    code_map = {'KEYWORD': default_cat}
    for code in codes:
        if code in code_map:
            continue
        # Try find by code (case-insensitive)
        cat = TagCategory.objects.filter(code__iexact=code).first()
        if not cat:
            # slugify to be safe; keep uppercase legacy codes if they are uppercase
            normalized = code.upper() if code.isupper() else slugify(code)
            title = code if code else 'Category'
            cat = TagCategory.objects.create(code=normalized, title=title)
        code_map[code] = cat

    # 3) Backfill Tag.category_ref and keep Tag.category in sync with TagCategory.code
    for t in Tag.objects.all():
        code = t.category or 'KEYWORD'
        cat = code_map.get(code) or TagCategory.objects.filter(code__iexact=code).first()
        if not cat:
            cat = default_cat
        t.category_ref_id = cat.id
        t.category = cat.code
        t.save(update_fields=['category_ref', 'category'])

def backwards(apps, schema_editor):
    # No destructive reverse; leave data as-is
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('project', '0048_tagcategory_alter_tag_category_alter_tag_description_and_more'),  # ← your 0048 filename
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
