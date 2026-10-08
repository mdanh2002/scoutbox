from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    """Mark 0.10.116 data repairs as pending without doing repair work in migration."""
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps = PortalSettings.objects.get_or_create(pk=1)[0]
    state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
    state['v010116_startup_safe_repairs'] = {
        'source_location_page_refetch': 'deferred_to_background_job',
        'focus_rebuild': 'deferred_to_background_job',
        'migration_network_calls_allowed': False,
        'migration_bulk_repairs_allowed': False,
        'recorded_at': timezone.now().isoformat(),
    }
    ps.focus_taxonomy_state = state
    ps.country_repair_version = ''
    ps.focus_taxonomy_version = ''
    ps.save(update_fields=['focus_taxonomy_state', 'country_repair_version', 'focus_taxonomy_version'])
    try:
        BackgroundJob.objects.filter(
            label__in=[
                'Repopulate country/location fields for 0.10.114',
                'Repopulate country/location fields for 0.10.115',
            ],
            status__in=['queued','running'],
        ).update(status='stopped', message='Superseded by ScoutBox 0.10.116 startup-safe background repair', finished_at=timezone.now())
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0135_v010114_evergreen_post_age')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
