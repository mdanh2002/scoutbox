from django.db import migrations


def log_upgrade(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.89').exists():
        AuditLog.objects.create(
            actor='system', action='version_upgraded', version='0.11.89',
            summary='ScoutBox upgraded to version 0.11.89.',
            metadata={'version': '0.11.89'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0160_v01188_ui_workflow_repairs')]
    operations = [migrations.RunPython(log_upgrade, migrations.RunPython.noop)]
