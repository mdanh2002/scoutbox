from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.106').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.106',
            summary='ScoutBox upgraded to version 0.11.106.',
            metadata={'release': '0.11.106'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0177_v011105_tracking_dialog_scan_height')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
