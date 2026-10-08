from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.112').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.112',
            summary='ScoutBox upgraded to version 0.11.112.',
            metadata={'release': '0.11.112'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0183_v011111_resource_hover_tracking_search')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
