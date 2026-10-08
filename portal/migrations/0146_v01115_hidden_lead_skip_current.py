from django.db import migrations
from django.utils import timezone


def mark_hidden_lead_reassessment_skip_current(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    now = timezone.now()
    for ps in PortalSettings.objects.all():
        state = dict(ps.focus_taxonomy_state or {})
        state['v01115_hidden_lead_minibrowser_reassessment_pending'] = True
        state['v01115_hidden_lead_minibrowser_reassessment'] = {
            'release': '0.11.15',
            'pending': True,
            'reason': 'Existing Hidden Leads reassessment now supports skip-current and resumable bounded progress.',
            'created_at': now.isoformat(),
        }
        # Supersede older passes so the post-health scheduler launches the resumable job.
        state['v0119_hidden_lead_minibrowser_reassessment_pending'] = False
        state['v01111_hidden_lead_minibrowser_reassessment_pending'] = False
        ps.focus_taxonomy_state = state
        ps.save(update_fields=['focus_taxonomy_state', 'updated_at'])
    qs = BackgroundJob.objects.filter(kind='filter_hidden_leads', status__in=['queued', 'running'], label__icontains='Reassess existing Hidden Leads')
    for job in qs:
        result = dict(job.result or {})
        result['superseded_by_release'] = '0.11.15'
        result['superseded_reason'] = 'Replaced by skip-current resumable Hidden Lead reassessment.'
        job.status = 'stopped'
        job.finished_at = now
        job.message = 'Stopped — replaced by 0.11.15 resumable reassessment'
        job.result = result
        job.save(update_fields=['status', 'finished_at', 'message', 'result'])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0145_v01111_bounded_hidden_lead_reassessment'),
    ]

    operations = [
        migrations.RunPython(mark_hidden_lead_reassessment_skip_current, migrations.RunPython.noop),
    ]
