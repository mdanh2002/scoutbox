from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    """Force the 0.10.118 Focus quality rebuild to run after web health.

    This migration is intentionally database-only: no Local AI, HTTP/page fetches,
    or bulk label rewriting is performed during startup. It only marks a
    version-gated rebuild request that the normal scheduler will enqueue as a
    visible Dashboard Activity job after the web process is healthy.
    """
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps = PortalSettings.objects.get_or_create(pk=1)[0]
    state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
    state['v010118_focus_quality_repair_pending'] = True
    state['v010118_focus_quality_repair'] = {
        'forced_rebuild_of_existing_groups': True,
        'reason': '0.10.117 did not enqueue the promised background rebuild on some installs',
        'database_only_migration': True,
        'dashboard_activity_required': True,
        'recorded_at': timezone.now().isoformat(),
    }
    # Keep a marker of the previous state for diagnostics, but make the scheduler
    # treat the taxonomy as stale even when every row already has a nonblank Focus.
    state['previous_focus_taxonomy_version_before_010118'] = str(getattr(ps, 'focus_taxonomy_version', '') or '')
    ps.focus_taxonomy_state = state
    ps.focus_taxonomy_version = ''
    ps.save(update_fields=['focus_taxonomy_state', 'focus_taxonomy_version'])
    try:
        BackgroundJob.objects.filter(
            label__icontains='Focus',
            status__in=['queued', 'running'],
        ).update(status='stopped', message='Superseded by ScoutBox 0.10.118 forced Focus taxonomy rebuild', finished_at=timezone.now())
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0138_v010117_focus_quality_repair')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
