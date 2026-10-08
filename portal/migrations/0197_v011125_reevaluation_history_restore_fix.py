from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.125').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.125',
            summary='ScoutBox upgraded to version 0.11.125.',
            metadata={'release': '0.11.125'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0196_v011124_reevaluation_result_clarity')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
