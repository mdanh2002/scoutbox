from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.127').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.127',
            summary='ScoutBox upgraded to version 0.11.127.',
            metadata={'release': '0.11.127'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0198_v011126_reevaluation_result_listview')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
