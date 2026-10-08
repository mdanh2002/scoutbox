from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.117').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.117',
            summary='ScoutBox upgraded to version 0.11.117.',
            metadata={'release': '0.11.117'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0188_v011116_discovery_quality_export')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
