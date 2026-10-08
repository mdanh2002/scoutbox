from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.150').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.150',summary='ScoutBox upgraded to version 0.11.150.',
            metadata={
                'release':'0.11.150',
                'diagnostic_export_period_alignment':True,
                'presentation_only':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0221_v011149_diagnostic_export_layout_polish')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
