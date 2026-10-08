from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.147').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.147',summary='ScoutBox upgraded to version 0.11.147.',
            metadata={
                'release':'0.11.147',
                'campaign_specific_balanced_admission':True,
                'direct_source_candidate_fairness':True,
                'searchapi_google_jobs_clean_query':True,
                'multilingual_query_integrity':True,
                'compact_filter_state':True,
                'granular_diagnostic_export':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0218_v011146_diagnostic_export_modal_width')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
