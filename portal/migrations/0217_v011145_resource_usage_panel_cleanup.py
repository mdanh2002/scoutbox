from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.145').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.145',summary='ScoutBox upgraded to version 0.11.145.',
            metadata={
                'release':'0.11.145',
                'resource_usage_telemetry_panel_removed':True,
                'telemetry_continuity_backend_retained':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0216_v011144_telemetry_continuity')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
