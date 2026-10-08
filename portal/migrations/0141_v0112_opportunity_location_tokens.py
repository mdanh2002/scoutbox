from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    """Force post-health Opportunity location-field reconciliation for 0.11.2.

    Database-only migration: it does not fetch pages, call AI, or repair rows during
    web startup. It only marks the background Dashboard Activity repair pending and
    supersedes older queued/running location repairs.
    """
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps = PortalSettings.objects.get_or_create(pk=1)[0]
    state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
    state['v0112_opportunity_location_tokens_pending'] = True
    state['v0112_opportunity_location_tokens'] = {
        'source_authoritative_role_location': True,
        'rebuilds_legacy_country_from_role_location': True,
        'removes_stale_expanded_region_country_tokens': True,
        'albania_filter_regression_guard': True,
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
                'Rebuild Opportunity location fields for 0.11.2',
            ],
            status__in=['queued', 'running'],
        ).update(status='stopped', message='Superseded by ScoutBox 0.11.2 Opportunity location-field reconciliation', finished_at=timezone.now())
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0140_v010119_source_location_reconcile')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
