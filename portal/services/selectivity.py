"""Central discovery/contact admission selectivity for ScoutBox 0.11.54.

The three controls are intentionally independent.  Basic entity-integrity checks remain
mandatory at every level; these policies only change how much relevance/identity evidence
is required before an otherwise valid record is admitted.
"""
from __future__ import annotations

import re

from portal.models import PortalSettings

OPPORTUNITY_LEVELS = {'broad', 'balanced', 'specialist'}
LEAD_LEVELS = {'broad', 'balanced', 'specialist'}
CONTACT_LEVELS = {'broad', 'balanced', 'verified'}

_LABELS = {
    'broad': 'Broad',
    'balanced': 'Balanced',
    'specialist': 'Specialist',
    'verified': 'Verified',
}

_GENERIC_SIGNAL_WORDS = {
    'job','jobs','role','roles','work','remote','engineer','engineering','developer','development',
    'software','system','systems','technical','technology','technologies','company','companies',
    'specialist','senior','junior','lead','manager','consultant','consulting','platform','product',
    'service','services','application','applications','team','teams','project','projects',
    # Broad technical words are useful in Balanced mode but are not sufficient by
    # themselves to admit a Specialist result.
    'embedded','firmware','hardware','linux','iot','security',
}


def _normalise(value, allowed, default='balanced'):
    value = str(value or '').strip().casefold()
    return value if value in allowed else default


def snapshot(settings=None):
    settings = settings or PortalSettings.objects.get_or_create(pk=1)[0]
    return {
        'opportunities': _normalise(getattr(settings, 'opportunity_selectivity', 'balanced'), OPPORTUNITY_LEVELS),
        'hidden_leads': _normalise(getattr(settings, 'lead_selectivity', 'balanced'), LEAD_LEVELS),
        'address_book': _normalise(getattr(settings, 'contact_selectivity', 'balanced'), CONTACT_LEVELS),
    }


def _run_snapshot():
    """Return the campaign-run snapshot when called from a discovery task.

    Import lazily to avoid model/service import cycles.  Background jobs that are not
    campaign-bound intentionally use the currently saved setting.
    """
    try:
        from .cloud_budget import usage_context
        ctx=usage_context() or {}
        direct=ctx.get('selectivity')
        if isinstance(direct,dict) and direct:
            return direct
        from portal.models import CampaignRun
        run_id = ctx.get('campaign_run_id')
        if not run_id:
            return {}
        criteria = CampaignRun.objects.filter(pk=run_id).values_list('criteria', flat=True).first() or {}
        saved = criteria.get('selectivity') if isinstance(criteria, dict) else {}
        return saved if isinstance(saved, dict) else {}
    except Exception:
        return {}


def current(kind, settings=None):
    aliases = {
        'opportunity': ('opportunities', OPPORTUNITY_LEVELS),
        'opportunities': ('opportunities', OPPORTUNITY_LEVELS),
        'lead': ('hidden_leads', LEAD_LEVELS),
        'hidden_lead': ('hidden_leads', LEAD_LEVELS),
        'hidden_leads': ('hidden_leads', LEAD_LEVELS),
        'contact': ('address_book', CONTACT_LEVELS),
        'address_book': ('address_book', CONTACT_LEVELS),
    }
    key, allowed = aliases.get(str(kind or '').strip().casefold(), ('opportunities', OPPORTUNITY_LEVELS))
    saved = _run_snapshot().get(key)
    if saved:
        return _normalise(saved, allowed)
    return snapshot(settings).get(key, 'balanced')


def label(value):
    return _LABELS.get(str(value or '').strip().casefold(), 'Balanced')


def opportunity_thresholds(level=None):
    level = _normalise(level or current('opportunities'), OPPORTUNITY_LEVELS)
    # Balanced now protects niche campaign identity while Broad retains the historical wide-net behavior.
    return {
        'broad': {'confidence': 55, 'relevance_confidence': 45, 'fit_score': 0, 'requires_specialist_anchor': False, 'requires_campaign_anchor': False},
        'balanced': {'confidence': 70, 'relevance_confidence': 65, 'fit_score': 55, 'requires_specialist_anchor': False, 'requires_campaign_anchor': True},
        'specialist': {'confidence': 80, 'relevance_confidence': 75, 'fit_score': 70, 'requires_specialist_anchor': True, 'requires_campaign_anchor': True},
    }[level]


def lead_policy(level=None):
    level = _normalise(level or current('hidden_leads'), LEAD_LEVELS)
    return {
        'broad': {'semantic_delta': -8, 'minibrowser_cutoff': 65, 'requires_specialist_anchor': False, 'requires_campaign_anchor': False, 'outreach_signal_min': 2, 'automatic_scan_new_cap': 10},
        'balanced': {'semantic_delta': 0, 'minibrowser_cutoff': 80, 'requires_specialist_anchor': False, 'requires_campaign_anchor': True, 'outreach_signal_min': 3, 'automatic_scan_new_cap': 5},
        'specialist': {'semantic_delta': 10, 'minibrowser_cutoff': 85, 'requires_specialist_anchor': True, 'requires_campaign_anchor': True, 'outreach_signal_min': 4, 'automatic_scan_new_cap': 4},
    }[level]


def contact_policy(level=None):
    level = _normalise(level or current('address_book'), CONTACT_LEVELS)
    return {
        'broad': {'minimum_confidence': 0, 'require_verified_person': False, 'allow_useful_shared': True},
        'balanced': {'minimum_confidence': 0, 'require_verified_person': False, 'allow_useful_shared': False},
        'verified': {'minimum_confidence': 80, 'require_verified_person': True, 'allow_useful_shared': False},
    }[level]


def instruction(kind, level=None):
    kind = str(kind or '').strip().casefold()
    level = level or current(kind)
    if kind in {'opportunity','opportunities'}:
        return {
            'broad': 'Selectivity is BROAD: accept credible adjacent technical work, but never unrelated business roles or invalid/non-job pages.',
            'balanced': 'Selectivity is BALANCED: require meaningful campaign-specific role or technology evidence in the actual vacancy; broad candidate-profile similarity alone is not enough.',
            'specialist': 'Selectivity is SPECIALIST: admit far fewer roles; the actual vacancy must show strong campaign-specific specialist work, not merely a technical employer or generic software/embedded adjacency.',
        }[_normalise(level, OPPORTUNITY_LEVELS)]
    if kind in {'lead','hidden_lead','hidden_leads'}:
        return {
            'broad': 'Lead selectivity is BROAD: adjacent but credible organizations may qualify, but there must still be a practical outreach/commercial signal; technical similarity alone is insufficient.',
            'balanced': 'Lead selectivity is BALANCED: require campaign-specific technical evidence plus a clear current reason to contact or track the organization, such as services, consulting, partnership, project, vendor, contractor or hiring evidence.',
            'specialist': 'Lead selectivity is SPECIALIST: admit far fewer organizations and require concrete campaign-specific technical evidence plus corroborating current outreach/commercial evidence.',
        }[_normalise(level, LEAD_LEVELS)]
    return {
        'broad': 'Contact admission is BROAD: useful named people and legitimate technical/recruiting shared routes may qualify.',
        'balanced': 'Contact admission is BALANCED: use the standard ScoutBox contact-admission rules.',
        'verified': 'Contact admission is VERIFIED: automatically add only contacts with strong person identity and organization-ownership evidence.',
    }[_normalise(level, CONTACT_LEVELS)]


def _phrases(value):
    out=[]
    for part in re.split(r'[\n,;|]+', str(value or '')):
        part=' '.join(part.split()).strip().casefold()
        if len(part) >= 3 and part not in out:
            out.append(part)
    return out[:40]


def specialist_alignment(campaign, title='', text='', *, kind='opportunity'):
    """Conservative deterministic anchor for Specialist mode.

    A Specialist result needs campaign evidence in the record itself.  Exact campaign
    phrases are strongest.  Otherwise require at least two meaningful campaign tokens,
    preventing a generic word such as "software" or "engineer" from admitting a row.
    """
    if campaign is None:
        return False, []
    title_norm=' '.join(str(title or '').split()).casefold()
    evidence=(' '.join(str(text or '').split()).casefold())[:30000]
    haystack=(title_norm+' '+evidence).strip()
    roles=_phrases(getattr(campaign,'role_families',''))
    tech=_phrases(getattr(campaign,'technologies',''))
    exact=[]
    for phrase in roles + tech:
        if len(phrase) >= 4 and phrase in haystack:
            exact.append(phrase)
    # A campaign role/technology phrase in the actual vacancy title is a strong anchor.
    # Generic technical words such as "embedded" or "firmware" do not qualify alone.
    title_exact=[p for p in roles + tech if len(p)>=4 and p in title_norm and p not in _GENERIC_SIGNAL_WORDS]
    if title_exact:
        return True, title_exact[:6]
    # In body text, only a genuinely specific multi-word phrase is sufficient by itself.
    # Single broad/specialist words must be corroborated by another campaign signal below.
    strong=[p for p in exact if ' ' in p and not all(w in _GENERIC_SIGNAL_WORDS for w in p.split())]
    if strong:
        return True, strong[:6]
    tokens=[]
    for phrase in roles + tech:
        for token in re.findall(r'[a-z0-9+#.\-]{4,}', phrase):
            if token not in _GENERIC_SIGNAL_WORDS and token not in tokens:
                tokens.append(token)
    hits=[t for t in tokens if re.search(r'(?<![a-z0-9])'+re.escape(t)+r'(?![a-z0-9])', haystack)]
    return len(hits)>=2, hits[:8]



def campaign_alignment(campaign, title='', text='', *, level='balanced', kind='opportunity'):
    """Return deterministic campaign-specific evidence for Balanced/Specialist gates.

    Balanced deliberately remains less strict than Specialist, but it must still prove
    that the record belongs to the campaign which found it. Candidate-profile-wide
    similarity is not enough to attach a generic software/data role to every niche run.
    """
    level=_normalise(level, OPPORTUNITY_LEVELS if kind=='opportunity' else LEAD_LEVELS)
    if level=='broad':
        return True, []
    strict_ok,strict_hits=specialist_alignment(campaign,title,text,kind=kind)
    if strict_ok or level=='specialist':
        return strict_ok,strict_hits
    if campaign is None:
        return False,[]
    title_norm=' '.join(str(title or '').split()).casefold()
    evidence=(' '.join(str(text or '').split()).casefold())[:30000]
    haystack=(title_norm+' '+evidence).strip()
    phrases=_phrases(getattr(campaign,'role_families',''))+_phrases(getattr(campaign,'technologies',''))
    # A campaign-specific phrase in the title/body is sufficient even when it contains
    # one broad word, provided the full phrase has at least two words.
    phrase_hits=[p for p in phrases if len(p)>=4 and p in haystack and ' ' in p]
    if phrase_hits:
        return True,phrase_hits[:8]
    specific=[]; niche=[]
    for phrase in phrases:
        for token in re.findall(r'[a-z0-9+#.\-]{4,}',phrase):
            if token in {'embedded','firmware','hardware','linux','iot','security','virtualization','virtualisation','emulation'}:
                if token not in niche: niche.append(token)
            elif token not in _GENERIC_SIGNAL_WORDS and token not in specific:
                specific.append(token)
    specific_hits=[t for t in specific if re.search(r'(?<![a-z0-9])'+re.escape(t)+r'(?![a-z0-9])',haystack)]
    niche_hits=[t for t in niche if re.search(r'(?<![a-z0-9])'+re.escape(t)+r'(?![a-z0-9])',haystack)]
    hits=list(dict.fromkeys(specific_hits+niche_hits))
    return bool(len(specific_hits)>=2 or (specific_hits and niche_hits)),hits[:8]

def contact_identity_verified(email, name='', evidence_text='', confidence=0):
    """Require direct person-name evidence for Verified automatic Address Book mode."""
    try:
        if int(confidence or 0) < 80:
            return False
    except Exception:
        return False
    supplied=' '.join(str(name or '').split()).strip()
    if not supplied:
        return False
    low=supplied.casefold()
    if low in {'contact','unknown','n/a','none','team','support','sales','recruiting','recruitment','hr','jobs','careers'}:
        return False
    words=re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", supplied)
    if len(words)<2:
        return False
    ev=' '.join(str(evidence_text or '').split()).casefold()
    # Verified mode deliberately refuses a name that exists only because the email local
    # part was mechanically title-cased.  The supplied name must appear in retained evidence.
    if low not in ev:
        compact=' '.join(words).casefold()
        if compact not in ev:
            return False
    return True
