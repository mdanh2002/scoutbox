from django.db import migrations
from django.utils import timezone


def mark_bounded_hidden_lead_reassessment(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    now = timezone.now()
    for ps in PortalSettings.objects.all():
        state = dict(getattr(ps, 'focus_taxonomy_state', {}) or {})
        state['v01111_hidden_lead_minibrowser_reassessment_pending'] = True
        state['v01111_hidden_lead_minibrowser_reassessment'] = {
            'release': '0.11.11',
            'pending': True,
            'reason': 'Bound existing Hidden Lead reassessment per lead so slow domains/AI calls cannot stall the whole pass.',
            'per_lead_seconds': 75,
            'per_page_timeout_seconds': 6,
            'timeouts_are_review_only': True,
            'protected_outreach_not_recycled': True,
            'marked_at': now.isoformat(),
        }
        # Re-run with the bounded worker even if 0.11.9/0.11.10 markers already exist.
        state['v0119_hidden_lead_minibrowser_reassessment_pending'] = False
        ps.focus_taxonomy_state = state
        ps.save(update_fields=['focus_taxonomy_state', 'updated_at'])
    BackgroundJob.objects.filter(
        kind='filter_hidden_leads',
        label__icontains='Reassess existing Hidden Leads',
        status__in=['queued', 'running'],
    ).update(
        status='stopped',
        finished_at=now,
        message='Superseded by 0.11.11 bounded Hidden Lead reassessment',
    )


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0144_v0119_hidden_lead_reassessment'),
    ]

    operations = [
        migrations.RunPython(mark_bounded_hidden_lead_reassessment, migrations.RunPython.noop),
    ]
