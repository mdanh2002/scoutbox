from django.db import migrations


def log_upgrade(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.88').exists():
        AuditLog.objects.create(
            actor='system', action='version_upgraded', version='0.11.88',
            summary='ScoutBox upgraded to version 0.11.88.',
            metadata={'version': '0.11.88'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0159_v01187_ui_and_telemetry_repairs')]
    operations = [migrations.RunPython(log_upgrade, migrations.RunPython.noop)]
