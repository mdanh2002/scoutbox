from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    """Force post-health source-location reconciliation for 0.10.119.

    Database-only migration: it does not fetch pages, call AI, or repair rows during
    web startup.  It only marks the background Dashboard Activity repair pending.
    """
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps = PortalSettings.objects.get_or_create(pk=1)[0]
    state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
    state['v010119_source_location_reconciliation_pending'] = True
    state['v010119_source_location_reconciliation'] = {
        'source_authoritative_mismatch_repair': True,
        'checks_clean_but_wrong_values': True,
        'does_not_skip_valid_region_names': True,
        'related_cards_ignored': True,
        'database_only_migration': True,
        'dashboard_activity_required': True,
        'recorded_at': timezone.now().isoformat(),
    }
    ps.focus_taxonomy_state = state
    ps.country_repair_version = ''
    ps.save(update_fields=['focus_taxonomy_state', 'country_repair_version'])
    try:
        BackgroundJob.objects.filter(
            label__in=[
                'Repopulate country/location fields for 0.10.116',
                'Reconcile source-authoritative locations for 0.10.119',
            ],
            status__in=['queued', 'running'],
        ).update(status='stopped', message='Superseded by ScoutBox 0.10.119 source-authoritative location reconciliation', finished_at=timezone.now())
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0139_v010118_force_focus_rebuild')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
