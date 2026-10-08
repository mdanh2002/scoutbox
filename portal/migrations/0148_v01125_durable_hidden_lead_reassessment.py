from django.db import migrations
from django.utils import timezone


PASS_KEY = 'hidden_lead_minibrowser_reassessment_pass'
SCHEMA = 'hidden_lead_minibrowser_admission_v1'
RELEASE = '0.11.25'


OLD_PENDING_KEYS = [
    'hidden_lead_minibrowser_reassessment_pending',
    'v0119_hidden_lead_minibrowser_reassessment_pending',
    'v01111_hidden_lead_minibrowser_reassessment_pending',
    'v01115_hidden_lead_minibrowser_reassessment_pending',
    'v01119_hidden_lead_minibrowser_reassessment_pending',
]


def mark_durable_hidden_lead_reassessment(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    now = timezone.now()
    now_iso = now.isoformat()
    active_ids = list(CompanyLead.objects.filter(
        user_deleted=False,
        deleted_at__isnull=True,
    ).order_by('pk').values_list('pk', flat=True))

    for ps in PortalSettings.objects.all():
        state = dict(ps.focus_taxonomy_state or {})
        existing = state.get(PASS_KEY)
        if not isinstance(existing, dict):
            existing = {}
        status = str(existing.get('status') or '').lower()
        if status == 'completed':
            # Do not force a completed durable pass to start over merely because the
            # container was rebuilt.  Only a future schema change/manual action should
            # create a new pass.
            for key in OLD_PENDING_KEYS:
                state[key] = False
            ps.focus_taxonomy_state = state
            ps.save(update_fields=['focus_taxonomy_state', 'updated_at'])
            continue
        target_ids = existing.get('target_ids')
        if not isinstance(target_ids, list) or not target_ids:
            target_ids = active_ids
        clean_ids = []
        seen = set()
        for value in target_ids:
            try:
                ident = int(value)
            except Exception:
                continue
            if ident in seen:
                continue
            seen.add(ident)
            clean_ids.append(ident)
        pass_state = dict(existing)
        pass_state.update({
            'pass_id': pass_state.get('pass_id') or f'{SCHEMA}:{now_iso}',
            'schema': SCHEMA,
            'release': RELEASE,
            'status': 'pending',
            'target_ids': clean_ids,
            'target_count': len(clean_ids),
            'resume_from_per_lead_state': True,
            'deletions_deferred_until_completed': True,
            'protected_outreach_not_recycled': True,
            'marked_at': pass_state.get('marked_at') or now_iso,
            'updated_at': now_iso,
            'reason': 'Durable Hidden Lead reassessment pass; resumes from per-lead ai_state after container restarts.',
        })
        state[PASS_KEY] = pass_state
        state['hidden_lead_minibrowser_reassessment_pending'] = True
        for key in OLD_PENDING_KEYS:
            if key != 'hidden_lead_minibrowser_reassessment_pending':
                state[key] = False
        ps.focus_taxonomy_state = state
        ps.save(update_fields=['focus_taxonomy_state', 'updated_at'])

    # Stop old transient jobs.  The next scheduler tick will create/revive one durable
    # job using the same per-lead completed state, so progress is preserved.
    qs = BackgroundJob.objects.filter(
        kind='filter_hidden_leads',
        label__icontains='Reassess existing Hidden Leads',
        status__in=['queued', 'running'],
    )
    for job in qs:
        result = dict(job.result or {})
        result['superseded_by_release'] = RELEASE
        result['superseded_reason'] = 'Replaced by durable-pass Hidden Lead reassessment resume.'
        job.status = 'stopped'
        job.finished_at = now
        job.message = 'Stopped — replaced by durable Hidden Lead reassessment pass'
        job.result = result
        job.save(update_fields=['status', 'finished_at', 'message', 'result'])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0147_v01119_resumable_hidden_lead_reassessment'),
    ]

    operations = [
        migrations.RunPython(mark_durable_hidden_lead_reassessment, migrations.RunPython.noop),
    ]
