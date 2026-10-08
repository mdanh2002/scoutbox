from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    """Mark 0.10.117 Focus quality repair pending without blocking startup."""
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps = PortalSettings.objects.get_or_create(pk=1)[0]
    state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
    state['v010117_focus_quality_repair_pending'] = True
    state['v010117_focus_quality_repair'] = {
        'ai_first_label_generation': True,
        'dynamic_label_evidence': True,
        'no_hard_coded_group_prerequisite_keywords': True,
        'namespace_independent': True,
        'forced_coverage_removed': True,
        'blank_preferred_over_misleading_focus': True,
        'migration_network_or_llm_calls_allowed': False,
        'recorded_at': timezone.now().isoformat(),
    }
    ps.focus_taxonomy_state = state
    ps.focus_taxonomy_version = ''
    ps.save(update_fields=['focus_taxonomy_state', 'focus_taxonomy_version'])
    try:
        BackgroundJob.objects.filter(
            label__icontains='Focus',
            status__in=['queued','running'],
        ).update(status='stopped', message='Superseded by ScoutBox 0.10.117 Focus quality repair', finished_at=timezone.now())
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0137_v010116_startup_safe_source_scoped_location')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
