from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.143').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.143',summary='ScoutBox upgraded to version 0.11.143.',
            metadata={
                'release':'0.11.143',
                'restart_interrupted_campaign_recovery':True,
                'restart_interrupted_background_job_recovery':True,
                'restart_stale_local_ai_lock_cleanup':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0214_v011142_facebook_page_title_wrap')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
