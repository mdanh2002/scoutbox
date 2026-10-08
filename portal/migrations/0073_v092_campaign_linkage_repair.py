from django.db import migrations


def _positive_int(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _metadata_campaign_ids(payload):
    ids = set()
    if not isinstance(payload, dict):
        return ids
    cid = _positive_int(payload.get('campaign_id'))
    if cid:
        ids.add(cid)
    raw_ids = payload.get('campaign_ids') or []
    if isinstance(raw_ids, (list, tuple)):
        for raw in raw_ids:
            cid = _positive_int(raw)
            if cid:
                ids.add(cid)
    return ids


def repair_campaign_links(apps, schema_editor):
    Campaign = apps.get_model('portal', 'Campaign')
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    Opportunity = apps.get_model('portal', 'Opportunity')
    CampaignRun = apps.get_model('portal', 'CampaignRun')
    valid_campaign_ids = set(Campaign.objects.values_list('pk', flat=True))

    # CampaignRun result IDs are the strongest historical attribution source because
    # they record exactly which Opportunities/Hidden Leads that campaign returned.
    for run in CampaignRun.objects.exclude(campaign_id__isnull=True).iterator(chunk_size=250):
        if run.campaign_id not in valid_campaign_ids or not isinstance(run.result, dict):
            continue
        opportunity_ids = [_positive_int(x) for x in (run.result.get('opportunity_ids') or [])]
        opportunity_ids = [x for x in opportunity_ids if x]
        lead_ids = [_positive_int(x) for x in (run.result.get('lead_ids') or [])]
        lead_ids = [x for x in lead_ids if x]
        for opportunity in Opportunity.objects.filter(pk__in=opportunity_ids).iterator(chunk_size=500):
            opportunity.campaigns.add(run.campaign_id)
        for lead in CompanyLead.objects.filter(pk__in=lead_ids).iterator(chunk_size=500):
            lead.campaigns.add(run.campaign_id)

    # Local campaign discovery persisted exact attribution in ai_state._usage even
    # in releases where a missing M2M row could make the detail page say Direct/manual.
    for lead in CompanyLead.objects.all().iterator(chunk_size=500):
        state = lead.ai_state if isinstance(lead.ai_state, dict) else {}
        wanted = _metadata_campaign_ids(state.get('_usage') or {}) & valid_campaign_ids
        if wanted:
            lead.campaigns.add(*sorted(wanted))

    # Opportunities created directly by discovery record campaign_id in extracted_facts.
    # Opportunities promoted from Hidden Leads can inherit the lead's repaired campaigns.
    lead_cache = {}
    for opportunity in Opportunity.objects.all().iterator(chunk_size=500):
        facts = opportunity.extracted_facts if isinstance(opportunity.extracted_facts, dict) else {}
        wanted = _metadata_campaign_ids(facts)
        lead_id = _positive_int(facts.get('market_study_lead_id'))
        if lead_id:
            if lead_id not in lead_cache:
                lead = CompanyLead.objects.filter(pk=lead_id).first()
                lead_cache[lead_id] = set(lead.campaigns.values_list('pk', flat=True)) if lead else set()
            wanted.update(lead_cache[lead_id])
        wanted &= valid_campaign_ids
        if wanted:
            opportunity.campaigns.add(*sorted(wanted))


def reverse_noop(apps, schema_editor):
    # Repaired links are valid provenance and should not be discarded on rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0072_v091_ai_request_timeouts'),
    ]

    operations = [
        migrations.RunPython(repair_campaign_links, reverse_noop),
    ]
