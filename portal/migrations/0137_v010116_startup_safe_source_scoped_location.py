from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    """Mark 0.10.116 source-scoped repairs pending without blocking startup."""
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps = PortalSettings.objects.get_or_create(pk=1)[0]
    state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
    state['v010116_source_scoped_location'] = {
        'current_role_location_field_first': True,
        'related_cards_ignored': True,
        'llm_body_override_blocked': True,
        'all_sources_not_jobicy_only': True,
        'background_dashboard_repair_pending': True,
        'migration_network_calls_allowed': False,
        'recorded_at': timezone.now().isoformat(),
    }
    ps.focus_taxonomy_state = state
    ps.country_repair_version = ''
    ps.focus_taxonomy_version = ''
    ps.save(update_fields=['focus_taxonomy_state','country_repair_version','focus_taxonomy_version'])
    try:
        BackgroundJob.objects.filter(
            label__in=['Repopulate country/location fields for 0.10.115','Repopulate country/location fields for 0.10.116'],
            status__in=['queued','running'],
        ).update(status='stopped', message='Superseded by ScoutBox 0.10.116 source-scoped location repair', finished_at=timezone.now())
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0136_v010115_async_source_location_repair')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
