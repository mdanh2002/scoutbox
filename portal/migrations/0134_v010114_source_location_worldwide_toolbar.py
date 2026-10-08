from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    """0.10.114 marker migration.

    Startup migrations must be database-only and fast.  The heavier repairs that were
    previously attempted here are now queued after web health by the scheduler so the
    portal can come up before any refetch/backfill work starts.
    """
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps = PortalSettings.objects.get_or_create(pk=1)[0]
    now = timezone.now()
    state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
    state['v010114_deferred_repairs'] = {
        'source_faithful_location_display': True,
        'worldwide_persisted_location_blocked': True,
        'focus_rebuild_deferred': True,
        'country_location_repair_deferred': True,
        'migration_network_calls_allowed': False,
        'recorded_at': now.isoformat(),
    }
    ps.focus_taxonomy_state = state
    ps.focus_taxonomy_version = ''
    ps.country_repair_version = ''
    ps.save(update_fields=['focus_taxonomy_state', 'focus_taxonomy_version', 'country_repair_version'])
    try:
        BackgroundJob.objects.create(
            kind='other',
            label='0.10.114 startup marker',
            status='completed',
            progress=100,
            message='Startup-safe marker completed. Data repairs are deferred to Dashboard Activity jobs after web health.',
            started_at=now,
            finished_at=timezone.now(),
            result={'release':'0.10.116','startup_safe':True,'deferred_repairs':True},
        )
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies=[('portal','0133_v010113_location_focus_contact_repair')]
    operations=[migrations.RunPython(forwards, migrations.RunPython.noop)]
