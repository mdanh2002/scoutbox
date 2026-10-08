from django.db import migrations
from django.utils import timezone
from datetime import timedelta


def release_stale_forum_and_provider_runs(apps, schema_editor):
    CampaignRun = apps.get_model('portal', 'CampaignRun')
    now = timezone.now()
    cutoff = now - timedelta(minutes=25)
    qs = CampaignRun.objects.filter(status='running').filter(heartbeat_at__lt=cutoff)
    qs = qs.filter(stage__icontains='forum') | qs.filter(message__icontains='forum') | qs.filter(stage__icontains='Searching')
    for run in qs.iterator():
        result = run.result if isinstance(run.result, dict) else {}
        result.update({
            'stopped_reason': 'upgrade_released_stale_discovery_run',
            'timeout_reason': 'Released stale discovery run after 0.10.74 independent Forum browse scheduler repair.',
            'released_at': now.isoformat(),
        })
        run.status = 'failed'
        run.finished_at = now
        run.heartbeat_at = now
        run.stage = 'stale_released'
        run.message = 'Released stale discovery run after upgrade'
        run.error = 'Released stale discovery run during 0.10.74 upgrade.'
        run.stall_reason = 'Released stale discovery run during 0.10.74 upgrade.'
        run.result = result
        run.save(update_fields=['status', 'finished_at', 'heartbeat_at', 'stage', 'message', 'error', 'stall_reason', 'result'])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0104_v01073_forum_query_stall'),
    ]

    operations = [
        migrations.RunPython(release_stale_forum_and_provider_runs, migrations.RunPython.noop),
    ]
