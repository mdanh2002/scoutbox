from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.95').exists():
        AuditLog.objects.create(
            actor='system',
            action='version_upgraded',
            version='0.11.95',
            summary='ScoutBox upgraded to version 0.11.95.',
            metadata={
                'version': '0.11.95',
                'release': '0.11.94 migration startup hotfix',
            },
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0166_v01194_telemetry_ui_followups')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
