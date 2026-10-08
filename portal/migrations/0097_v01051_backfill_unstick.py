from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    now = timezone.now()
    # The legacy 0.10.41 startup repair is best-effort historical cleanup. If an
    # installation upgraded through several rapid patch releases, an orphaned queued
    # retry can keep the dashboard in a permanent "waiting for Local Discovery" state.
    # Mark the release repair complete during the 0.10.51 migration so startup will
    # not requeue it and any old visible Automatic task disappears as active work.
    for settings_row in PortalSettings.objects.all():
        if str(getattr(settings_row, 'release_backfill_version', '') or '') != '0.10.41':
            settings_row.release_backfill_version = '0.10.41'
            settings_row.save(update_fields=['release_backfill_version', 'updated_at'])
    for job in BackgroundJob.objects.filter(label='0.10.41 upgrade backfill', status__in=['queued', 'running']):
        result = dict(job.result or {})
        result.update({
            'release': '0.10.41',
            'state': 'completed_by_01051_migration',
            'network_heavy_repair_skipped': True,
            'reason': 'Finalized by 0.10.51 so the legacy release backfill cannot stay stuck behind Local Discovery.',
            'completed_at': now.isoformat(),
            'fixed_by_release': '0.10.51',
        })
        job.status = 'completed'
        job.progress = 100
        job.finished_at = now
        job.message = '0.10.41 backfill finalized by 0.10.51 migration'
        job.error = ''
        job.result = result
        job.save(update_fields=['status', 'progress', 'finished_at', 'message', 'error', 'result'])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0096_v01045_release_repair')]
    operations = [migrations.RunPython(forwards, backwards)]
