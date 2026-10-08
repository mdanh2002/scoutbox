from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.123').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.123',
            summary='ScoutBox upgraded to version 0.11.123.',
            metadata={'release': '0.11.123'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0194_v011122_cloud_reevaluation_prompts')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
