from django.db import migrations


def forwards(apps, schema_editor):
    FacebookPage=apps.get_model('portal','FacebookPage')
    AuditLog=apps.get_model('portal','AuditLog')

    # 0.11.91 could exhaust retries because title discovery was still coupled to
    # Facebook relevance validation. Re-open blank-title rows once so 0.11.92's
    # identity-only resolver can repair them automatically.
    FacebookPage.objects.filter(enabled=True,deleted_at__isnull=True,page_title='').update(
        validation_state='pending',
        validation_reason='Page-title identity lookup queued after the 0.11.92 repair.',
        title_retry_count=0,
        title_retry_started_at=None,
    )

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.92').exists():
        AuditLog.objects.create(
            actor='system', action='version_upgraded', version='0.11.92',
            summary='ScoutBox upgraded to version 0.11.92.',
            metadata={'version':'0.11.92'},
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0163_v01191_retry_and_titles')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
