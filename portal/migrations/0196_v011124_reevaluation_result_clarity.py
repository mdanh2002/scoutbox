from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.124').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.124',
            summary='ScoutBox upgraded to version 0.11.124.',
            metadata={'release': '0.11.124'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0195_v011123_reevaluation_dialog_cleanup')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
