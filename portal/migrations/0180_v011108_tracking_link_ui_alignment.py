from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.108').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.108',
            summary='ScoutBox upgraded to version 0.11.108.',
            metadata={'release': '0.11.108'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0179_v011107_tracking_dialog_polish')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
