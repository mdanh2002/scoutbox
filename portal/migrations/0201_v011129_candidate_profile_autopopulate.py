from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.129').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.129',
            summary='ScoutBox upgraded to version 0.11.129.',
            metadata={'release': '0.11.129'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0200_v011128_resume_grounded_reevaluation')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
