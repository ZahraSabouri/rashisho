# rahi-api-main/apps/project/migrations/0061_seed_teambuilding_settings.py
"""
Seeds TeamBuildingSettings for stages 1..4 and control types ('formation','team_page')
to avoid 'missing row' false negatives in guards. Keeps defaults; admins can toggle later.
"""
from django.db import migrations

def seed_settings(apps, schema_editor):
    TBS = apps.get_model('project', 'TeamBuildingSettings')
    # Keep model defaults; we only ensure rows exist.
    for stage in (1, 2, 3, 4):
        for control in ('formation', 'team_page'):
            TBS.objects.get_or_create(
                stage=stage,
                control_type=control,
                defaults={
                    # conservative defaults matching your serializer expectations
                    'is_enabled': False,
                    'min_team_size': 2,
                    'max_team_size': 6,
                    'prevent_repeat_teammates': True,
                    'allow_auto_completion': True,
                    'formation_deadline_hours': 24,
                },
            )

class Migration(migrations.Migration):

    dependencies = [
        ('project', '0060_alter_teamrequest_request_type_emergencyactionlog_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_settings, migrations.RunPython.noop),
    ]
