from django.db import migrations


STALE_CONTACT_ERROR = 'Contact matching query does not exist.'
SKIP_MESSAGE = 'Skipped — Address Book contact no longer exists'


def cleanup_stale_contact_research(apps, schema_editor):
    """Retire stale Address Book research jobs that were never AI/model failures.

    A contact can be deleted or purged after its enrichment job is queued. Older workers
    called Contact.objects.get(), so that normal lifecycle race became a failed
    company_enrichment placeholder in AI Requests. Convert those historical jobs to a
    completed/skipped state and remove only their placeholder AI Request rows.
    """
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    AIRequestLog = apps.get_model('portal', 'AIRequestLog')

    stale_jobs = BackgroundJob.objects.filter(
        kind='company_research',
        status='failed',
        label__startswith='Address Book company research:',
    )
    for job in stale_jobs.iterator(chunk_size=200):
        error = str(job.error or job.message or '').strip()
        if error.rstrip('.') != STALE_CONTACT_ERROR.rstrip('.'):
            continue
        result = dict(job.result or {})
        result.update({'state': 'stale_contact', 'skipped': True})
        BackgroundJob.objects.filter(pk=job.pk).update(
            status='completed',
            progress=100,
            message=SKIP_MESSAGE,
            error='',
            result=result,
        )
        AIRequestLog.objects.filter(
            subject_type='background_job',
            subject_id=str(job.pk),
            stage='company_enrichment',
            metadata__placeholder=True,
        ).delete()

    # Also remove orphaned placeholder rows when the corresponding BackgroundJob was
    # already purged. Never touch real provider/model request logs.
    stale_logs = AIRequestLog.objects.filter(
        subject_type='background_job',
        stage='company_enrichment',
        status='failed',
        subject_label__startswith='Address Book company research:',
        metadata__placeholder=True,
    )
    for row in stale_logs.iterator(chunk_size=200):
        error = str(row.error or '').strip()
        if error.rstrip('.') == STALE_CONTACT_ERROR.rstrip('.'):
            row.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0066_v08106_company_info_badge_repair'),
    ]

    operations = [
        migrations.RunPython(cleanup_stale_contact_research, migrations.RunPython.noop),
    ]
