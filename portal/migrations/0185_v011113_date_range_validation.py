from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.113').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.113',
            summary='ScoutBox upgraded to version 0.11.113.',
            metadata={'release': '0.11.113'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0184_v011112_date_filter_icon_state')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
