from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.151').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.151',summary='ScoutBox upgraded to version 0.11.151.',
            metadata={
                'release':'0.11.151',
                'query_language_code_normalization':True,
                'historical_usage_metrics_rewritten':False,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0222_v011150_diagnostic_export_period_alignment')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
