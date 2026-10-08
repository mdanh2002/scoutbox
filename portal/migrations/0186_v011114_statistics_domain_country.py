from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.114').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.114',
            summary='ScoutBox upgraded to version 0.11.114.',
            metadata={'release': '0.11.114'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0185_v011113_date_range_validation')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
