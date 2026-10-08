from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def release_local_ai_contention_runs(apps, schema_editor):
    CampaignRun = apps.get_model('portal', 'CampaignRun')
    now = timezone.now()
    qs = CampaignRun.objects.filter(status__in=['queued', 'running']).filter(
        Q(stage__icontains='local AI') |
        Q(message__icontains='local AI') |
        Q(stage__icontains='first filter') |
        Q(message__icontains='first filter') |
        Q(stage__icontains='query planning') |
        Q(message__icontains='query planning')
    )
    for run in qs.iterator():
        result = run.result if isinstance(run.result, dict) else {}
        result.update({
            'stopped_reason': 'upgrade_released_local_ai_contention',
            'timeout_reason': 'Released active Local AI contention run during 0.10.75 upgrade so the scheduler can requeue under the new bounded lane policy.',
            'deferred_local_ai': True,
            'retryable': True,
            'released_at': now.isoformat(),
        })
        criteria = run.criteria if isinstance(run.criteria, dict) else {}
        criteria.update({'deferred_local_ai': True, 'retryable': True})
        run.status = 'stopped'
        run.finished_at = now
        run.heartbeat_at = now
        run.stage = 'Local AI deferred'
        run.message = 'Released Local AI contention run after upgrade; scheduler will retry later'
        run.error = ''
        run.stall_reason = ''
        run.result = result
        run.criteria = criteria
        run.save(update_fields=['status', 'finished_at', 'heartbeat_at', 'stage', 'message', 'error', 'stall_reason', 'result', 'criteria'])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0105_v01074_independent_forum_browse'),
    ]

    operations = [
        migrations.RunPython(release_local_ai_contention_runs, migrations.RunPython.noop),
    ]
