from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.152').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.152',summary='ScoutBox upgraded to version 0.11.152.',
            metadata={
                'release':'0.11.152',
                'query_language_unknown_faceting':True,
                'historical_usage_metrics_rewritten':False,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0223_v011151_query_language_code_normalization')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
