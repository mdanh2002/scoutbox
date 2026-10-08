from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.146').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.146',summary='ScoutBox upgraded to version 0.11.146.',
            metadata={
                'release':'0.11.146',
                'diagnostic_export_modal_compacted':True,
                'diagnostic_export_modal_max_width_px':540,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0217_v011145_resource_usage_panel_cleanup')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
