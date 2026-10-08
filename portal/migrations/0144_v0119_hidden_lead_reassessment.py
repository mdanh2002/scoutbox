from django.db import migrations


def mark_hidden_lead_reassessment_pending(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    BackgroundJob = apps.get_model('portal', 'BackgroundJob')
    ps, _ = PortalSettings.objects.get_or_create(pk=1)
    state = dict(getattr(ps, 'focus_taxonomy_state', None) or {})
    state['v0119_hidden_lead_minibrowser_reassessment_pending'] = True
    state['v0119_hidden_lead_minibrowser_reassessment'] = {
        'release': '0.11.9',
        'status': 'pending',
        'reason': 'Existing Hidden Leads must pass the 0.11.8 minibrowser admission gate before weak rows are recycled.',
        'deletions_deferred_until_completed': True,
        'protected_outreach_not_recycled': True,
    }
    ps.focus_taxonomy_state = state
    ps.save(update_fields=['focus_taxonomy_state', 'updated_at'])
    BackgroundJob.objects.filter(
        kind='filter_hidden_leads',
        label='Reassess existing Hidden Leads for 0.11.9',
        status__in=['queued', 'running'],
    ).update(status='stopped', message='Superseded by migration marker for 0.11.9 Hidden Lead reassessment')


class Migration(migrations.Migration):
    dependencies = [('portal', '0143_v0115_source_readonly_location_repair')]

    operations = [
        migrations.RunPython(mark_hidden_lead_reassessment_pending, migrations.RunPython.noop),
    ]
