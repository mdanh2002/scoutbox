from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.111').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.111',
            summary='ScoutBox upgraded to version 0.11.111.',
            metadata={'release': '0.11.111'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0182_v011110_tracking_invalid_link_message')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
