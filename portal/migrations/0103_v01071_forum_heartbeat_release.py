from django.db import migrations
from django.utils import timezone
from datetime import timedelta


def release_stale_forum_runs(apps, schema_editor):
    CampaignRun = apps.get_model('portal', 'CampaignRun')
    now = timezone.now()
    cutoff = now - timedelta(minutes=30)
    qs = CampaignRun.objects.filter(status='running', heartbeat_at__lt=cutoff)
    qs = qs.filter(stage__icontains='forum') | qs.filter(message__icontains='forum')
    for run in qs.iterator():
        meta = run.metadata if isinstance(run.metadata, dict) else {}
        meta.update({
            'stopped_reason': 'upgrade_stale_forum_run_released',
            'timeout_reason': 'Released stale Forum browsing run after 0.10.71 heartbeat repair.',
            'released_at': now.isoformat(),
        })
        run.status = 'failed'
        run.finished_at = now
        run.heartbeat_at = now
        run.stage = 'stale_released'
        run.message = 'Released stale Forum browsing run after upgrade'
        run.error = 'Released stale Forum browsing run during 0.10.71 upgrade.'
        run.stall_reason = 'Released stale Forum browsing run during 0.10.71 upgrade.'
        run.metadata = meta
        run.save(update_fields=['status', 'finished_at', 'heartbeat_at', 'stage', 'message', 'error', 'stall_reason', 'metadata'])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0102_v01066_forum_unstarve'),
    ]

    operations = [
        migrations.RunPython(release_stale_forum_runs, migrations.RunPython.noop),
    ]
