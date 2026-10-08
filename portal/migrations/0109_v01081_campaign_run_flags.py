from django.db import migrations


def normalize_campaign_run_flags(apps, schema_editor):
    """Normalize scheduler-critical CampaignRun JSON flags without deleting history."""
    CampaignRun = apps.get_model('portal', 'CampaignRun')
    pending = []
    for run in CampaignRun.objects.all().only('pk', 'criteria').iterator(chunk_size=500):
        criteria = dict(run.criteria or {})
        changed = False
        if 'forum_only' not in criteria:
            criteria['forum_only'] = bool(criteria.get('run_kind') == 'forum_only')
            changed = True
        if 'deferred_local_ai' not in criteria:
            criteria['deferred_local_ai'] = False
            changed = True
        if 'run_kind' not in criteria:
            criteria['run_kind'] = 'forum_only' if criteria.get('forum_only') else 'primary'
            changed = True
        if changed:
            run.criteria = criteria
            pending.append(run)
            if len(pending) >= 500:
                CampaignRun.objects.bulk_update(pending, ['criteria'], batch_size=500)
                pending.clear()
    if pending:
        CampaignRun.objects.bulk_update(pending, ['criteria'], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0108_v01079_contact_generic_repair'),
    ]

    operations = [
        migrations.RunPython(normalize_campaign_run_flags, migrations.RunPython.noop),
    ]
