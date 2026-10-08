from django.db import migrations
from django.utils import timezone

PASS_KEY = 'hidden_lead_minibrowser_reassessment_pass'
RELEASE = '0.11.26'


def canonicalize_hidden_lead_reassessment(apps, schema_editor):
    """DB-only cleanup: keep one transient job for the durable reassessment pass.

    No page fetching, AI calls or reassessment work is performed here. The worker will
    resume from the durable pass/per-lead state after web health.
    """
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    now = timezone.now()

    pass_id = ''
    for ps in PortalSettings.objects.all():
        state = dict(ps.focus_taxonomy_state or {})
        pass_state = state.get(PASS_KEY)
        if isinstance(pass_state, dict):
            pass_state = dict(pass_state)
            pass_id = str(pass_state.get('pass_id') or pass_id or '')
            pass_state['release'] = RELEASE
            pass_state['canonical_progress_source'] = True
            pass_state['updated_by_release'] = RELEASE
            state[PASS_KEY] = pass_state
            # A real durable pass owns this flag. Old version-specific flags must not
            # force the pass back to pending/rerun on every scheduler tick.
            for key in (
                'v0119_hidden_lead_minibrowser_reassessment_pending',
                'v01111_hidden_lead_minibrowser_reassessment_pending',
                'v01115_hidden_lead_minibrowser_reassessment_pending',
                'v01119_hidden_lead_minibrowser_reassessment_pending',
            ):
                state[key] = False
            if str(pass_state.get('status') or '').lower() == 'completed':
                state['hidden_lead_minibrowser_reassessment_pending'] = False
            ps.focus_taxonomy_state = state
            ps.save(update_fields=['focus_taxonomy_state', 'updated_at'])

    active = []
    for job in BackgroundJob.objects.filter(kind='filter_hidden_leads', status__in=['queued', 'running']).order_by('-pk'):
        result = job.result if isinstance(job.result, dict) else {}
        if result.get('hidden_lead_minibrowser_reassessment') or str(job.label or '').startswith('Reassess existing Hidden Leads'):
            active.append(job)

    if len(active) <= 1:
        return

    def rank(job):
        result = job.result if isinstance(job.result, dict) else {}
        matches = 1 if pass_id and str(result.get('pass_id') or '') == pass_id else 0
        try:
            processed = int(result.get('processed') or 0)
        except Exception:
            processed = 0
        return (matches, processed, int(job.progress or 0), int(job.pk or 0))

    canonical = max(active, key=rank)
    for job in active:
        if job.pk == canonical.pk:
            continue
        result = dict(job.result or {}) if isinstance(job.result, dict) else {}
        result['superseded_by_release'] = RELEASE
        result['superseded_by_job_id'] = canonical.pk
        result['superseded_by_pass_id'] = pass_id
        job.status = 'stopped'
        job.finished_at = now
        job.message = 'Stopped — duplicate Hidden Lead reassessment worker'
        job.result = result
        job.save(update_fields=['status', 'finished_at', 'message', 'result'])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0148_v01125_durable_hidden_lead_reassessment'),
    ]

    operations = [
        migrations.RunPython(canonicalize_hidden_lead_reassessment, migrations.RunPython.noop),
    ]
