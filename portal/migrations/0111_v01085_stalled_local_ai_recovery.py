from datetime import timedelta
from django.db import migrations
from django.utils import timezone


def recover_upgrade_stalls(apps, schema_editor):
    CampaignRun = apps.get_model('portal', 'CampaignRun')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    AIRequestLog = apps.get_model('portal', 'AIRequestLog')
    now = timezone.now()
    run_cutoff = now - timedelta(minutes=15)
    job_cutoff = now - timedelta(minutes=20)

    for run in CampaignRun.objects.filter(status='running').filter(heartbeat_at__lt=run_cutoff).order_by('started_at', 'created_at')[:500]:
        result = dict(run.result or {})
        result.update({
            'stopped_reason': 'upgrade_recovered_stalled_local_ai',
            'recovered_by': 'v0.10.85 migration',
            'last_heartbeat_at': run.heartbeat_at.isoformat() if run.heartbeat_at else '',
        })
        CampaignRun.objects.filter(pk=run.pk, status='running').update(
            status='failed',
            finished_at=now,
            message='Recovered stale Local AI run after upgrade',
            error='Run had no heartbeat for at least 15 minutes during v0.10.85 upgrade.',
            stall_reason='Recovered stale Local AI run after upgrade',
            result=result,
        )

    stale_jobs = BackgroundJob.objects.filter(
        status='running',
        kind__in=['company_research', 'summarize', 'enrich'],
        started_at__lt=job_cutoff,
    ).order_by('started_at', 'created_at')[:500]
    stale_job_ids = []
    for job in stale_jobs:
        stale_job_ids.append(job.pk)
        result = dict(job.result or {})
        result.update({
            'state': 'upgrade_recovered_stalled_local_ai',
            'recovered_by': 'v0.10.85 migration',
        })
        BackgroundJob.objects.filter(pk=job.pk, status='running').update(
            status='failed',
            finished_at=now,
            progress=100,
            message='Recovered stale AI background job after upgrade',
            error='AI background job had been running for at least 20 minutes during v0.10.85 upgrade.',
            result=result,
        )
    if stale_job_ids:
        AIRequestLog.objects.filter(
            subject_type='background_job',
            subject_id__in=[str(x) for x in stale_job_ids],
            status__in=['queued', 'running'],
        ).update(
            status='failed',
            ok=False,
            error='Recovered stale AI background job after v0.10.85 upgrade.',
        )


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0110_v01084_max_concurrent_campaigns'),
    ]

    operations = [
        migrations.RunPython(recover_upgrade_stalls, migrations.RunPython.noop),
    ]
