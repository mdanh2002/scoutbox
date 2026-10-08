from datetime import timedelta

from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def release_stale_campaign_runs(apps, schema_editor):
    CampaignRun = apps.get_model('portal', 'CampaignRun')
    now = timezone.now()
    running_cutoff = now - timedelta(minutes=90)
    queued_cutoff = now - timedelta(minutes=45)

    stale_running = CampaignRun.objects.filter(status='running').filter(
        Q(heartbeat_at__lt=running_cutoff) |
        Q(heartbeat_at__isnull=True, started_at__lt=running_cutoff) |
        Q(heartbeat_at__isnull=True, started_at__isnull=True, created_at__lt=running_cutoff)
    )
    for run in stale_running.iterator():
        last = run.heartbeat_at or run.started_at or run.created_at
        result = dict(run.result or {})
        result.update({
            'stopped_reason': 'upgrade_stale_campaign_released',
            'upgrade_release': '0.10.66',
            'last_heartbeat_at': last.isoformat() if last else '',
            'timeout_reason': 'Released stale running campaign so scheduled Forum browsing is not blocked after upgrade.',
        })
        CampaignRun.objects.filter(pk=run.pk, status='running').update(
            status='failed', finished_at=now, heartbeat_at=now,
            message='Campaign stale after upgrade',
            error='Released stale running campaign during 0.10.66 upgrade.',
            stall_reason='Released stale running campaign during 0.10.66 upgrade.',
            result=result,
        )

    stale_queued = CampaignRun.objects.filter(status='queued', started_at__isnull=True, created_at__lt=queued_cutoff)
    for run in stale_queued.iterator():
        result = dict(run.result or {})
        result.update({
            'stopped_reason': 'upgrade_stale_queue_released',
            'upgrade_release': '0.10.66',
            'timeout_reason': 'Released stale queued campaign so scheduled discovery can continue after upgrade.',
        })
        CampaignRun.objects.filter(pk=run.pk, status='queued', started_at__isnull=True).update(
            status='failed', finished_at=now, heartbeat_at=now,
            message='Campaign queue stale after upgrade',
            error='Released stale queued campaign during 0.10.66 upgrade.',
            stall_reason='Released stale queued campaign during 0.10.66 upgrade.',
            result=result,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0101_v01059_forum_sources'),
    ]

    operations = [
        migrations.RunPython(release_stale_campaign_runs, migrations.RunPython.noop),
    ]
