from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.100').exists():
        AuditLog.objects.create(
            actor='system',
            action='version_upgraded',
            version='0.11.100',
            summary='ScoutBox upgraded to version 0.11.100.',
            metadata={
                'version': '0.11.100',
                'release': 'dashboard route hotfix, tracking editor alignment, statistics and audit polish',
            },
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0171_v01199_ui_consistency')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
