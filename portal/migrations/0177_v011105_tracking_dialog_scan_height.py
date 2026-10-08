from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.105').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.105',
            summary='ScoutBox upgraded to version 0.11.105.',
            metadata={'release': '0.11.105'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0176_v011104_tracking_dialog_natural_height')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
