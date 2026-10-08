from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.96').exists():
        AuditLog.objects.create(
            actor='system',
            action='version_upgraded',
            version='0.11.96',
            summary='ScoutBox upgraded to version 0.11.96.',
            metadata={
                'version': '0.11.96',
                'release': 'tracking allocation, localized discovery, statistics and list UI repairs',
            },
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0167_v01195_migration_hotfix')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
