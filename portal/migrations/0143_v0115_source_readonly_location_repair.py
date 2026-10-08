from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    """Force post-health source-readonly location reconciliation for 0.11.5.

    Database-only migration: no HTTP, no Local AI, and no row repair during web
    startup.  It only resets the location repair version so the Dashboard
    Activity job can re-fetch source-backed records after the app is healthy.
    """
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps = PortalSettings.objects.get_or_create(pk=1)[0]
    state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
    state['v0115_source_readonly_location_pending'] = True
    state['v0115_source_readonly_location'] = {
        'read_only_detail_location_fields': True,
        'source_visible_region_beats_structured_country_array': True,
        'jobicy_remote_from_europe_regression_guard': True,
        'no_region_expansion_in_detail_editors': True,
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
                'Rebuild Opportunity location fields for 0.11.2',
                'Rebuild source-readonly location fields for 0.11.5',
            ],
            status__in=['queued', 'running'],
        ).update(status='stopped', message='Superseded by ScoutBox 0.11.5 source-readonly location reconciliation', finished_at=timezone.now())
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0142_v0113_focus_label_evidence_repair')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
