from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.119').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.119',
            summary='ScoutBox upgraded to version 0.11.119.',
            metadata={'release': '0.11.119'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0190_v011118_parallel_reevaluation_import')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
