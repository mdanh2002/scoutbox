from django.db import migrations
from django.utils import timezone


def mark_resumable_hidden_lead_reassessment(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    now = timezone.now()
    for ps in PortalSettings.objects.all():
        state = dict(ps.focus_taxonomy_state or {})
        state['v01119_hidden_lead_minibrowser_reassessment_pending'] = True
        state['v01119_hidden_lead_minibrowser_reassessment'] = {
            'release': '0.11.19',
            'pending': True,
            'reason': 'Existing Hidden Lead reassessment now resumes from durable per-lead results and hides empty placeholder result cards.',
            'resume_from_per_lead_state': True,
            'deletions_deferred_until_completed': True,
            'protected_outreach_not_recycled': True,
            'marked_at': now.isoformat(),
        }
        state['v01115_hidden_lead_minibrowser_reassessment_pending'] = False
        state['v01111_hidden_lead_minibrowser_reassessment_pending'] = False
        ps.focus_taxonomy_state = state
        ps.save(update_fields=['focus_taxonomy_state', 'updated_at'])
    qs = BackgroundJob.objects.filter(
        kind='filter_hidden_leads',
        label__icontains='Reassess existing Hidden Leads',
        status__in=['queued', 'running'],
    )
    for job in qs:
        result = dict(job.result or {})
        result['superseded_by_release'] = '0.11.19'
        result['superseded_reason'] = 'Replaced by resumable 0.11.19 Hidden Lead reassessment.'
        job.status = 'stopped'
        job.finished_at = now
        job.message = 'Stopped — replaced by 0.11.19 resumable reassessment'
        job.result = result
        job.save(update_fields=['status', 'finished_at', 'message', 'result'])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0146_v01115_hidden_lead_skip_current'),
    ]

    operations = [
        migrations.RunPython(mark_resumable_hidden_lead_reassessment, migrations.RunPython.noop),
    ]
