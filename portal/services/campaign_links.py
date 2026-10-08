"""Campaign-attribution helpers for Opportunities and Hidden Leads.

Campaign relations are the canonical UI/filtering source.  A few legacy/promotion
paths also carry exact campaign provenance in JSON metadata; these helpers use
that provenance only to repair a missing relation, never to guess one.
"""
from portal.models import Campaign, CompanyLead


def _campaign_id(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _metadata_campaign_ids(payload):
    ids = set()
    if not isinstance(payload, dict):
        return ids
    cid = _campaign_id(payload.get('campaign_id'))
    if cid:
        ids.add(cid)
    for raw in payload.get('campaign_ids') or []:
        cid = _campaign_id(raw)
        if cid:
            ids.add(cid)
    return ids


def repair_lead_campaign_links(lead):
    """Restore exact campaign relations already recorded in a lead's usage metadata."""
    wanted = set()
    state = lead.ai_state if isinstance(getattr(lead, 'ai_state', None), dict) else {}
    wanted.update(_metadata_campaign_ids(state.get('_usage') or {}))
    if not wanted:
        return []
    valid = set(Campaign.objects.filter(pk__in=wanted).values_list('pk', flat=True))
    existing = set(lead.campaigns.values_list('pk', flat=True))
    missing = sorted(valid - existing)
    if missing:
        lead.campaigns.add(*missing)
    if not getattr(lead,'origin_campaign_id',None):
        usage=state.get('_usage') if isinstance(state.get('_usage'),dict) else {}
        explicit=_campaign_id(usage.get('campaign_id'))
        preferred=explicit if explicit in valid else (next(iter(valid)) if len(valid)==1 else None)
        if preferred:
            lead.origin_campaign_id=preferred
            lead.save(update_fields=['origin_campaign','updated_at'])
    return sorted(existing | valid)


def repair_opportunity_campaign_links(opportunity):
    """Restore exact campaign relations from discovery/lead provenance when missing."""
    wanted = set()
    facts = opportunity.extracted_facts if isinstance(getattr(opportunity, 'extracted_facts', None), dict) else {}
    wanted.update(_metadata_campaign_ids(facts))

    lead_id = _campaign_id(facts.get('market_study_lead_id'))
    if lead_id:
        lead = CompanyLead.objects.filter(pk=lead_id).first()
        if lead:
            repair_lead_campaign_links(lead)
            wanted.update(lead.campaigns.values_list('pk', flat=True))

    if not wanted:
        return []
    valid = set(Campaign.objects.filter(pk__in=wanted).values_list('pk', flat=True))
    existing = set(opportunity.campaigns.values_list('pk', flat=True))
    missing = sorted(valid - existing)
    if missing:
        opportunity.campaigns.add(*missing)
    if not getattr(opportunity,'origin_campaign_id',None):
        preferred=None
        cid=_campaign_id(facts.get('campaign_id'))
        if cid in valid:
            preferred=cid
        elif lead_id:
            lead=CompanyLead.objects.filter(pk=lead_id).only('origin_campaign_id').first()
            preferred=getattr(lead,'origin_campaign_id',None) if lead else None
        if not preferred and len(valid)==1:
            preferred=next(iter(valid))
        if preferred:
            opportunity.origin_campaign_id=preferred
            opportunity.save(update_fields=['origin_campaign','updated_at'])
    return sorted(existing | valid)


def copy_lead_campaigns_to_opportunity(lead, opportunity):
    """Preserve campaign attribution when a Hidden Lead becomes an Opportunity."""
    repair_lead_campaign_links(lead)
    campaign_ids = list(lead.campaigns.values_list('pk', flat=True))
    if campaign_ids:
        opportunity.campaigns.add(*campaign_ids)
    if not getattr(opportunity,'origin_campaign_id',None):
        origin=getattr(lead,'origin_campaign_id',None)
        if origin:
            opportunity.origin_campaign_id=origin
            opportunity.save(update_fields=['origin_campaign','updated_at'])
    return campaign_ids


def _campaign_assignment_evidence(entity):
    """Return retained entity text suitable for a conservative rediscovery attribution check."""
    parts=[]
    for name in ('title','company','description','list_highlight','recommendation_reason','summary','match_summary','evidence'):
        value=getattr(entity,name,'')
        if value:
            parts.append(str(value))
    facts=getattr(entity,'extracted_facts',None)
    if isinstance(facts,dict):
        for key in ('fit_reason','highlight','raw_search_snippet','role_location','search_query'):
            value=facts.get(key)
            if value:
                parts.append(str(value))
    return ' '.join(parts)[:30000]


def attribute_campaign(entity, campaign):
    """Record campaign provenance without letting generic rediscovery pollute niche labels.

    First discovery is already protected by the persistence admission gate.  Additional
    campaign labels are added only when the retained entity itself contains meaningful
    evidence for that campaign. This prevents one generic full-stack/data role from slowly
    acquiring every niche campaign merely because several broad queries rediscovered it.
    """
    if not entity or not campaign:
        return entity
    existing_ids=set(entity.campaigns.values_list('pk',flat=True))
    if getattr(campaign,'pk',None) in existing_ids:
        return entity
    if existing_ids:
        try:
            from .selectivity import current as selectivity_current, campaign_alignment
            level=selectivity_current('hidden_leads' if isinstance(entity,CompanyLead) else 'opportunities')
            title=getattr(entity,'title','') or getattr(entity,'company','') or ''
            allowed,hits=campaign_alignment(
                campaign,title,_campaign_assignment_evidence(entity),level=level,
                kind='hidden_lead' if isinstance(entity,CompanyLead) else 'opportunity',
            )
            if not allowed:
                try:
                    from portal.models import UsageMetric
                    UsageMetric.objects.create(
                        category='discovery_filter',provider='campaign_attribution',stage='campaign_attribution',requests=1,
                        metadata={'entity_type':'hidden_lead' if isinstance(entity,CompanyLead) else 'opportunity','entity_id':getattr(entity,'pk',None),'campaign_id':getattr(campaign,'pk',None),'campaign':getattr(campaign,'name',''),'decision':'skip','reason':'missing_campaign_specific_evidence','hits':hits},
                    )
                except Exception:
                    pass
                return entity
        except Exception:
            # Additional provenance is optional; fail closed rather than polluting a niche
            # campaign when a legacy entity cannot be evaluated deterministically.
            return entity
    entity.campaigns.add(campaign)
    if not getattr(entity,'origin_campaign_id',None):
        entity.origin_campaign=campaign
        entity.save(update_fields=['origin_campaign','updated_at'])
    return entity
