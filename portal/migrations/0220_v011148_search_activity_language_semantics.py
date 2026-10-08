from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.148').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.148',summary='ScoutBox upgraded to version 0.11.148.',
            metadata={
                'release':'0.11.148',
                'search_activity_market_language_split':True,
                'query_language_request_telemetry':True,
                'historical_language_unknown_not_inferred':True,
                'diagnostic_export_ui_refinement':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0219_v011147_discovery_quality_and_diagnostics')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
