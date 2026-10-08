from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.128').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.128',
            summary='ScoutBox upgraded to version 0.11.128.',
            metadata={'release': '0.11.128'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0199_v011127_reevaluation_xlsx_layout')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
