from django.db import migrations
from django.utils import timezone


def mark_focus_label_evidence_repair_pending(apps, schema_editor):
    """Mark 0.11.3 Focus label evidence repair pending without blocking startup."""
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps, _ = PortalSettings.objects.get_or_create(pk=1)
    state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
    state['v0113_focus_label_evidence_repair_pending'] = True
    state['v0113_focus_label_evidence_repair'] = {
        'release': '0.11.3',
        'marked_at': timezone.now().isoformat(),
        'startup_safe': True,
        'reason': 'Rebuild Focus labels with evidence-anchored critical token validation for small/outlier groups.',
    }
    ps.focus_taxonomy_state = state
    ps.focus_taxonomy_version = ''
    ps.save(update_fields=['focus_taxonomy_state', 'focus_taxonomy_version'])
    BackgroundJob.objects.filter(
        kind='other',
        label__icontains='Focus',
        status__in=['queued', 'running'],
    ).update(status='stopped', message='Superseded by ScoutBox 0.11.3 Focus label evidence repair', finished_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0141_v0112_opportunity_location_tokens'),
    ]

    operations = [
        migrations.RunPython(mark_focus_label_evidence_repair_pending, migrations.RunPython.noop),
    ]
