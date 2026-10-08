from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.110').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.110',
            summary='ScoutBox upgraded to version 0.11.110.',
            metadata={'release': '0.11.110'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0181_v011109_tracking_close_alignment')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
