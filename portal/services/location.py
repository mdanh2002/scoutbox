"""Deterministic country/location resolution for ScoutBox records.

Candidate/profile operating locations are intentionally excluded. Role/page/source
location evidence may now produce multiple countries or recruiter regions such as
Europe and APAC. Worldwide remains blocked from persisted locations; company HQ remains only a fallback for remote roles whose
posting has no role-country restriction.
"""
from __future__ import annotations

import re
from typing import Any

import requests
from django.utils import timezone

from .cold import infer_country
from .content_quality import extract_role_location, normalize_remote_constraints
from .location_values import parse_location_items, normalize_location_items, legacy_location_text, REGION_DEFS


_BAD_ROLE_LOCATION_RE=re.compile(r'(?i)\b(?:work type|compensation|new remote from|related remote jobs|matched by job category|keep exploring|opportunity details|apply now)\b')
_JOBICY_STOP_RE=re.compile(r'(?i)^\s*(?:salary|department|employment|experience|published|apply before|listing views|application actions|opportunity details|about this role|work type|compensation)\b')

def _strip_markdown_location_line(value):
    value=_clean(value,500)
    # Convert markdown links in Jobicy snapshots: [USA](...), [Canada](...) -> USA, Canada.
    labels=re.findall(r'\[([^\]]{1,80})\]\([^\)]*job-region[^\)]*\)', value)
    if labels:
        return ', '.join(_clean(x,80) for x in labels if _clean(x,80))[:240]
    value=re.sub(r'\[([^\]]+)\]\([^\)]*\)', r'\1', value)
    value=re.sub(r'\s*,\s*', ', ', value)
    return _clean(value,240)

def _bad_role_location(value):
    value=_clean(value,500)
    if not value:
        return True
    if _BAD_ROLE_LOCATION_RE.search(value):
        return True
    if value.count('{') or value.count('[') >= 2:
        return True
    return False

def _jobicy_snapshot_role_location(page_text):
    """Extract Jobicy's current-role ``Remote from`` value.

    Jobicy pages can arrive as sectioned text, markdown-like text, or a compact
    flattened line.  Prefer the human-facing Role snapshot/alert location over
    structured JobPosting applicantLocation arrays because Jobicy expands broad
    regions such as Europe into long country arrays that are not suitable as the
    ScoutBox display value.
    """
    raw=str(page_text or '')[:50000]
    if not raw:
        return ''
    # HTML snapshots preserve the authoritative visible Role snapshot even when the
    # plain-text extractor drops its <dt>/<dd> pair. Read that exact pair first.
    html_match=re.search(r'(?is)<dt[^>]*>\s*Remote\s+from\s*</dt>\s*<dd[^>]*>\s*(?:<a[^>]+job-region/[^>]*>)?\s*([^<]{2,120})',raw)
    if html_match:
        val=_strip_markdown_location_line(html_match.group(1))
        items=parse_location_items(val,source='jobicy_snapshot_html',evidence=html_match.group(0))
        if items:
            return legacy_location_text(items)[:240]
    # Capture the complete visible value before considering individual region aliases.
    # The previous fast path returned the first match (APAC) and discarded a sibling
    # region (EMEA) from the same ``Remote from`` field.
    segment_match=re.search(
        r'(?is)\bRemote\s+from\s*(?:[:\-|]\s*)?(.{2,420}?)(?=\n\s*(?:Salary|Department|Employment|Experience|Published|Apply before|Listing views|Application actions|Opportunity details)\b|\s+(?:Salary|Department|Employment|Experience|Published|Apply before|Listing views|Application actions|Opportunity details)\b|$)',
        raw,
    )
    if segment_match:
        segment=segment_match.group(1)
        linked=_strip_markdown_location_line(segment)
        items=parse_location_items(linked,source='jobicy_snapshot',evidence=segment)
        if items:
            return legacy_location_text(items)[:240]
    # Fast path for broad recruiter regions. Some fetchers flatten the visible field
    # or insert markdown/newlines between ``Remote from`` and the region link.
    region_aliases=[]
    for label,spec in REGION_DEFS.items():
        if str(spec.get('code') or '') == 'WORLDWIDE':
            continue
        region_aliases.extend([label, *list(spec.get('aliases', ()))])
    for alias in sorted({str(x) for x in region_aliases if str(x).strip()}, key=len, reverse=True):
        m=re.search(r'(?is)\bRemote\s+from\s*(?:[:\-|]\s*)?(?:\[\s*)?('+re.escape(alias)+r')(?:\s*\])?', raw)
        if m:
            val=_strip_markdown_location_line(m.group(1))
            if val and not _bad_role_location(val):
                return val[:240]
    lines=[ln.strip() for ln in raw.replace('\r','\n').splitlines()]
    for idx,line in enumerate(lines):
        if re.fullmatch(r'(?i)remote\s+from\s*[:\-|]?', line or ''):
            for ln in lines[idx+1:idx+10]:
                if not ln:
                    continue
                if _JOBICY_STOP_RE.search(ln):
                    break
                val=_strip_markdown_location_line(ln)
                if val and not _bad_role_location(val):
                    return val[:240]
        m=re.match(r'(?i)^\s*remote\s+from\s*[:\-|]?\s+(.{2,220})$', line or '')
        if m:
            val=_strip_markdown_location_line(m.group(1))
            val=re.split(r'(?i)\s+(?:Salary|Department|Employment|Experience|Published|Apply before|Listing views|Application actions)\b', val)[0]
            val=_strip_markdown_location_line(val)
            if val and not _bad_role_location(val):
                return val[:240]
    # Compact fetchers may flatten the Role snapshot into one line:
    # "Role snapshot Hiring now Remote from Europe Salary Undisclosed ...".
    compact=' '.join(raw.replace('|',' ').split())
    m=re.search(r'(?i)\bRemote\s+from\s+(.{2,220}?)(?=\s+(?:Salary|Department|Employment|Experience|Published|Apply before|Listing views|Application actions|Opportunity details)\b|$)', compact)
    if m:
        val=_strip_markdown_location_line(m.group(1))
        if val and not _bad_role_location(val):
            return val[:240]
    return ''


_PAGE_SECTION_BOUNDARY_RE=re.compile(r'(?im)^\s*(?:related jobs|related remote jobs|recommended jobs|similar jobs|more opportunities|keep exploring|matched by job category|about the company|company overview|other jobs at|more jobs from|footer|privacy policy|terms of service)\b')
_ROLE_FIELD_STOP_RE=re.compile(r'(?i)^\s*(?:salary|department|employment|experience|published|apply before|listing views|application actions|opportunity details|about this role|about the job|responsibilities|requirements|qualifications|benefits|work type|compensation)\b')


def _current_job_scope(page_text):
    raw=str(page_text or '').replace('\r','\n')[:70000]
    m=_PAGE_SECTION_BOUNDARY_RE.search(raw)
    if m:
        raw=raw[:m.start()]
    return raw


def _snapshot_role_location(page_text):
    """Extract the current post's visible location field for any job page.

    This intentionally reads only a labelled location field and the immediately following
    line(s), then stops before salary/department/body/related sections.  It avoids using
    later page prose such as "customers worldwide" or other job cards.
    """
    jobicy=_jobicy_snapshot_role_location(page_text)
    if jobicy:
        return jobicy
    raw=_current_job_scope(page_text)
    lines=[ln.strip() for ln in raw.splitlines()]
    label_re=re.compile(r'(?i)^(?:remote from|job location|work location|role location|location requirements?|eligible locations?|workplace|office|location)\s*[:|\-]?\s*(.*)$')
    for idx,line in enumerate(lines):
        m=label_re.match(line or '')
        if not m:
            continue
        vals=[]
        inline=_strip_markdown_location_line(m.group(1) or '')
        if inline and not _bad_role_location(inline) and inline.casefold() not in _REMOTE_PLACEHOLDERS:
            vals.append(inline)
        if not vals:
            for ln in lines[idx+1:idx+6]:
                if not ln:
                    continue
                if _ROLE_FIELD_STOP_RE.search(ln) or _PAGE_SECTION_BOUNDARY_RE.search(ln):
                    break
                val=_strip_markdown_location_line(ln)
                if val and not _bad_role_location(val) and val.casefold() not in _REMOTE_PLACEHOLDERS:
                    vals.append(val)
                    break
        if vals:
            return ', '.join(vals)[:240]
    # Role-scoped eligibility sentences can be used only after labelled fields fail.
    for pattern in (
        r'(?i)\b(?:this|the) role is (?:fully remote;?\s*)?(?:only\s+)?open to candidates based in\s+([^\n.;]{2,180})',
        r'(?i)\b(?:this|the) role is (?:available|open) in (?:the following locations?:\s*)?([^\n.;]{2,180})',
        r'(?i)\b(?:applicants?|candidates?)\s+(?:must|should|need to)\s+be\s+(?:located|based)\s+in\s+([^\n.;]{2,180})',
        r'(?i)\b(?:applicants?|candidates?)\s+(?:must|should|need to)\s+(?:live|reside)\s+in\s+([^\n.;]{2,180})',
    ):
        m=re.search(pattern,raw[:30000])
        if m:
            val=_strip_markdown_location_line(m.group(1))
            if val and not _bad_role_location(val) and val.casefold() not in _REMOTE_PLACEHOLDERS:
                return val[:240]
    return ''


def _alert_location_from_text(page_text, target_url=''):
    """Decode board alert/application URLs that carry the current role location."""
    raw=str(page_text or '')[:70000]
    # Alert links often appear near the application block after the company card but
    # before related jobs.  Do not cut at About the company for this fallback; only
    # prevent drift into related/recommended cards.
    m=_PAGE_SECTION_BOUNDARY_RE.search(raw)
    if m and re.search(r'(?i)related|recommended|more opportunities|keep exploring|matched by job category', m.group(0) or ''):
        raw=raw[:m.start()]
    try:
        from urllib.parse import unquote_plus
        for m in re.finditer(r'alert_location=([^&\s\)]{2,500})', raw):
            val=unquote_plus(m.group(1))
            val=re.sub(r'[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF\ufe0f]+',' ',val)
            val=_strip_markdown_location_line(val)
            if val and not _bad_role_location(val) and val.casefold() not in _REMOTE_PLACEHOLDERS:
                return val[:240]
    except Exception:
        pass
    return ''

_REMOTE_PLACEHOLDERS={
    '', 'remote', 'fully remote', 'hybrid', 'on-site', 'onsite', 'not specified',
    'unspecified', 'unknown', 'n/a', 'na', 'none', 'null', 'tbd',
}


def _clean(value: Any, limit=500):
    return ' '.join(str(value or '').replace('\n',' ').replace('\xa0',' ').split()).strip()[:limit]


def _items_from_hint(value, *, source='page_location'):
    value=_clean(value,2000)
    if not value or value.casefold() in _REMOTE_PLACEHOLDERS:
        return []
    items=parse_location_items(value, source=source, evidence=value)
    if items:
        return items
    country=infer_country('', '', location_hint=value)
    return parse_location_items(country, source=source, evidence=value) if country else []


def _country_from_hint(value):
    return legacy_location_text(_items_from_hint(value))


def _remote_role(remote_text='', facts=None, page_text=''):
    facts=facts if isinstance(facts,dict) else {}
    review=facts.get('local_pre_persistence_review') if isinstance(facts.get('local_pre_persistence_review'),dict) else {}
    state=_clean(review.get('remote_status'),40).casefold()
    if state in {'remote','fully_remote'}:
        return True
    if state in {'hybrid','onsite','on-site'}:
        return False
    text=_clean(remote_text,500).casefold()
    if re.search(r'\bhybrid\b|\bon[- ]?site\b|\bonsite\b',text):
        return False
    if re.search(r'\bremote\b|\bwork from home\b|\bhome[- ]based\b|\bworldwide\b|\banywhere\b',text):
        return True
    page=_clean(page_text,20000).casefold()
    return bool(re.search(r'\b(?:remote[- ]first|fully remote|remote role|remote position|work remotely|work from home|remote work)\b',page))


def company_hq_country_from_intel(company_intel):
    """Return a legacy location string only from explicitly company-location/HQ fields."""
    intel=company_intel if isinstance(company_intel,dict) else {}
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    for key in ('headquarters','hq','company_location','location','base_location'):
        value=_clean(structured.get(key),500)
        items=_items_from_hint(value, source=f'company_intel.structured.{key}')
        if items and not any((x.get('label') or '').casefold() in {'worldwide','global'} for x in items):
            return legacy_location_text(items), value, f'company_intel.structured.{key}'
    for row in intel.get('facts') or []:
        if not isinstance(row,dict):
            continue
        label=_clean(row.get('label'),80).casefold()
        if label not in {'location','company location','headquarters','hq','base','based in'}:
            continue
        value=_clean(row.get('value'),500)
        items=_items_from_hint(value, source=f'company_intel.fact.{label}')
        if items and not any((x.get('label') or '').casefold() in {'worldwide','global'} for x in items):
            return legacy_location_text(items), value, f'company_intel.fact.{label}'
    return '', '', ''


def company_hq_country_from_text(page_text):
    """Extract an explicitly labelled employer HQ/base location from visible page text."""
    raw=str(page_text or '')[:50000]
    patterns=(
        r'(?im)(?:^|\n)\s*(?:HQ|Headquarters|Company location|Company HQ|Registered office)\s*[:\-]?\s*([^\n|•]{2,180})',
        r'(?i)\b(?:HQ|Headquarters|Company HQ)\s*[:\-]?\s*([^|•\n]{2,160})',
    )
    for pattern in patterns:
        for match in re.finditer(pattern,raw):
            value=_clean(match.group(1),180)
            items=_items_from_hint(value, source='page_company_hq')
            if items and not any((x.get('label') or '').casefold() in {'worldwide','global'} for x in items):
                return legacy_location_text(items), value, 'page_company_hq'
    return '', '', ''


def _provenance(locations, source, evidence='', *, fallback=False):
    locations=normalize_location_items(locations)
    return {
        'country': legacy_location_text(locations),
        'locations': locations,
        'source':_clean(source,80),
        'evidence':_clean(evidence,500),
        'fallback':bool(fallback),
        'policy':'0.11.2 source-authoritative role-location and filter-token reconciliation; current role location fields override retained/LLM/related-card values',
        'resolved_at':timezone.now().isoformat(),
    }


def _result(items, role_location, source, evidence, *, fallback=False):
    items=normalize_location_items(items, source=source, evidence=evidence)
    return {'country':legacy_location_text(items),'locations':items,'role_location':_clean(role_location,240),'provenance':_provenance(items,source,evidence,fallback=fallback)}


def resolve_opportunity_location(*, target_url='', inspected=None, page_title='', page_text='',
                                 direct_location_hint='', market_location_hint='', stored_role_location='', remote_text='',
                                 company_intel=None, facts=None):
    """Resolve Opportunity country/locations and display role location from hard evidence."""
    inspected=inspected if isinstance(inspected,dict) else {}
    facts=facts if isinstance(facts,dict) else {}
    text=(str(page_title or '')+'\n'+str(page_text or '')).strip()

    structured_hint=inspected.get('jobposting_location') or ''
    # Recruiter/source-facing current-job location is authoritative for display for all
    # boards and ATS pages, not just Jobicy.  It must beat structured arrays, LLM/body
    # inference, and any related-job/card content.
    # Only a tightly scoped labelled current-job field is authoritative here.
    # Do not fall through to the broad extractor before the alert/direct/structured
    # checks, because broad page text can contain related-job cards or marketing prose.
    visible_role=_snapshot_role_location(page_text)
    # Some page-text extractors omit Jobicy's compact Role snapshot while retaining the
    # source HTML in extracted facts. Prefer that current-page field before structured
    # applicant-location arrays, which can expand EMEA/Europe into dozens of countries.
    retained_html=str(facts.get('description_html') or '') if isinstance(facts,dict) else ''
    if not visible_role and retained_html:
        visible_role=_snapshot_role_location(retained_html)
    alert_role=_alert_location_from_text(page_text, target_url=target_url)
    for display, source in ((visible_role,'current_role_location_field'), (alert_role,'current_role_alert_location')):
        if display and not _bad_role_location(display):
            items=_items_from_hint(display, source=source)
            if items:
                return _result(items, display, source, display)

    # The direct/source hint is trusted only after current-page fields fail.  It is still
    # bounded by duplicate-merge validation in adapter repair paths.
    direct_hint=_clean(direct_location_hint,1200)
    if direct_hint and direct_hint.casefold() not in _REMOTE_PLACEHOLDERS and not _bad_role_location(direct_hint):
        items=_items_from_hint(direct_hint, source='direct_source_location')
        if items:
            display=extract_role_location('',direct_hint) or direct_hint
            return _result(items, display, 'direct_source_location', direct_hint)

    scoped_page=_current_job_scope(page_text)
    role_location=extract_role_location(scoped_page, structured_hint)
    items=_items_from_hint(structured_hint, source='structured_jobposting')
    if items:
        return _result(items, role_location or structured_hint, 'structured_jobposting', structured_hint)

    visible_role=role_location or visible_role
    if visible_role and not _bad_role_location(visible_role):
        items=_items_from_hint(visible_role, source='explicit_page_role_location')
        if items:
            return _result(items, visible_role, 'explicit_page_role_location', visible_role)

    retained=_clean(stored_role_location,240)
    if retained and retained.casefold() not in _REMOTE_PLACEHOLDERS and not _bad_role_location(retained):
        items=_items_from_hint(retained, source='retained_role_location')
        if items:
            return _result(items, retained, 'retained_role_location', retained)

    constraints=normalize_remote_constraints(page_text,remote_text) or {}
    country=_clean(constraints.get('country'),120)
    if country:
        evidence=_clean(constraints.get('reason') or constraints.get('label'),500)
        items=_items_from_hint(country, source='explicit_remote_eligibility')
        if items:
            return _result(items, visible_role, 'explicit_remote_eligibility', evidence or country)

    # A local-board market is stronger fallback evidence than broad page/domain inference.
    # This specifically prevents a localized board result (for example hk.jobsdb.com) from
    # inheriting an unrelated US country mention from navigation, corporate boilerplate or
    # provider metadata. It is used only when no explicit role/structured/eligibility location
    # above resolved the vacancy, and its fallback provenance remains auditable.
    market_hint=_clean(market_location_hint,240)
    if market_hint and market_hint.casefold() not in {'worldwide','global','remote'}:
        items=_items_from_hint(market_hint, source='discovery_market_source_fallback')
        if items:
            return _result(items, visible_role, 'discovery_market_source_fallback', market_hint, fallback=True)

    country=infer_country(target_url,(str(page_title or '')+'\n'+_current_job_scope(page_text)).strip(),strict=True)
    if country:
        items=parse_location_items(country, source='explicit_page_location', evidence=country)
        return _result(items, visible_role, 'explicit_page_location', country)

    if _remote_role(remote_text,facts,page_text):
        country,evidence,source=company_hq_country_from_text(page_text)
        if not country:
            country,evidence,source=company_hq_country_from_intel(company_intel)
        items=parse_location_items(country, source=source, evidence=evidence) if country else []
        if items:
            return _result(items, visible_role, source, evidence, fallback=True)

    return {'country':'','locations':[],'role_location':visible_role[:240],
            'provenance':_provenance([],'unresolved','No explicit role country or eligible remote-HQ fallback was found.')}


def legacy_country_is_untrusted(record):
    current=_clean(getattr(record,'country',''),120)
    if not current:
        return False
    facts=getattr(record,'extracted_facts',{}) or {}
    if not isinstance(facts,dict):
        return False
    prov=facts.get('country_provenance')
    if isinstance(prov,dict) and _clean(prov.get('source'),80):
        return False
    guesses=[]
    review=facts.get('local_pre_persistence_review')
    if isinstance(review,dict): guesses.append(review.get('company_country'))
    cloud=facts.get('cloud_research')
    if isinstance(cloud,dict): guesses.append(cloud.get('country'))
    return any(_clean(value,120).casefold()==current.casefold() for value in guesses if _clean(value,120))


def _direct_role_location_recovery(record, timeout=8):
    facts=getattr(record,'extracted_facts',{}) or {}
    acq=facts.get('acquisition') if isinstance(facts,dict) and isinstance(facts.get('acquisition'),dict) else {}
    adapter=_clean(acq.get('adapter'),80).casefold()
    title=_clean(getattr(record,'title',''),300)
    company=_clean(getattr(record,'company',''),220)
    item_id=_clean(acq.get('source_item_id'),160)
    headers={'Accept':'application/json,text/plain,*/*','User-Agent':'ScoutBox/0.11.2 (+location filter token reconciliation)'}
    try:
        if adapter=='himalayas' and title:
            response=requests.get('https://himalayas.app/jobs/api/search',params={'q':title,'sort':'recent','page':1},headers=headers,timeout=timeout)
            response.raise_for_status(); data=response.json() if response.content else {}
            for item in data.get('jobs') or []:
                if not isinstance(item,dict): continue
                same_id=bool(item_id and _clean(item.get('guid'),160)==item_id)
                same_company=not company or _clean(item.get('companyName'),220).casefold()==company.casefold()
                same_title=_clean(item.get('title'),300).casefold()==title.casefold()
                if same_id or (same_company and same_title):
                    restrictions=[_clean(x.get('name') if isinstance(x,dict) else x,120) for x in (item.get('locationRestrictions') or [])]
                    restrictions=[x for x in restrictions if x]
                    if restrictions:
                        return ', '.join(restrictions[:8])[:800], 'himalayas_api'
        elif adapter=='jobicy':
            response=requests.get('https://jobicy.com/api/v2/remote-jobs',params={'count':200},headers=headers,timeout=timeout)
            response.raise_for_status(); data=response.json() if response.content else {}
            for item in data.get('jobs') or []:
                if not isinstance(item,dict): continue
                same_id=bool(item_id and _clean(item.get('id'),160)==item_id)
                same_company=not company or _clean(item.get('companyName'),220).casefold()==company.casefold()
                same_title=_clean(item.get('jobTitle'),300).casefold()==title.casefold()
                if same_id or (same_company and same_title):
                    value=_clean(item.get('jobGeo'),500)
                    if value: return value,'jobicy_api'
    except Exception:
        pass
    return '',''


def repopulate_country_fields(*, progress=None, fetch_pages=True):
    """Repair country/location fields across Opportunities, Hidden Leads and Contacts."""
    from portal.models import Opportunity, CompanyLead, Contact
    from .pagefetch import fetch_target

    stats={'opportunities_checked':0,'opportunities_updated':0,'opportunities_cleared':0,
           'hidden_leads_checked':0,'hidden_leads_updated':0,'contacts_checked':0,'contacts_updated':0,
           'page_fetches':0,'direct_location_recoveries':0,'errors':0}
    total=Opportunity.objects.count()+CompanyLead.objects.count()+Contact.objects.count()
    done=0

    for record in Opportunity.objects.order_by('pk').iterator(chunk_size=100):
        stats['opportunities_checked']+=1; done+=1
        try:
            facts=dict(record.extracted_facts or {})
            direct_hint=_clean(facts.get('direct_role_location_hint'),1200)
            page_text=str(record.description or '')
            page_title=str(record.title or '')
            result=resolve_opportunity_location(target_url=record.target_url or record.url, inspected={},
                page_title=page_title,page_text=page_text,direct_location_hint=direct_hint,
                stored_role_location=record.role_location,remote_text=record.remote_text,
                company_intel=record.company_intel,facts=facts)
            suspect=legacy_country_is_untrusted(record)
            if not result.get('country'):
                recovered,recovery_source=_direct_role_location_recovery(record)
                if recovered:
                    stats['direct_location_recoveries']+=1
                    direct_hint=recovered; facts['direct_role_location_hint']=recovered; facts['direct_role_location_hint_source']=recovery_source
                    result=resolve_opportunity_location(target_url=record.target_url or record.url,inspected={},page_title=page_title,page_text=page_text,
                        direct_location_hint=recovered,stored_role_location=record.role_location,remote_text=record.remote_text,company_intel=record.company_intel,facts=facts)
            prior_prov=facts.get('country_provenance') if isinstance(facts.get('country_provenance'),dict) else {}
            stored_role=_clean(record.role_location,240)
            # 0.11.5: reconcile source-backed rows against the current source page,
            # even when the stored value is a clean but wrong country/region such as LATAM.
            # Earlier repairs only targeted visibly malformed values and could therefore
            # leave stale/cross-record locations unchanged.
            source_url=str(record.target_url or record.url or '')
            source_backed=bool(source_url and re.search(r'(?i)https?://', source_url))
            needs_source_fidelity_refresh=(
                source_backed or
                stored_role.startswith(('[','{')) or
                _bad_role_location(stored_role) or
                _clean(prior_prov.get('source'),80) in {'structured_jobposting','retained_role_location','direct_source_location'}
            )
            if fetch_pages and needs_source_fidelity_refresh and source_url:
                stats['page_fetches']+=1
                fetched=fetch_target(source_url,record.title,record.raw_search_snippet or '',timeout=8)
                if fetched.get('ok'):
                    # Treat the fetched current page as the authority. Pass the old stored
                    # value only for debug fallback; source/header extraction wins and clean
                    # mismatches are overwritten.
                    result=resolve_opportunity_location(target_url=fetched.get('target_url') or source_url,
                        inspected=fetched,page_title=fetched.get('title') or record.title,page_text=fetched.get('text') or page_text,direct_location_hint=direct_hint,
                        stored_role_location=record.role_location,remote_text=record.remote_text,company_intel=record.company_intel,facts=facts)
                    facts['source_location_reconciliation']={
                        'release':'0.11.5','fetched':True,'source_url':source_url[:500],
                        'before_role_location':stored_role,'after_role_location':_clean(result.get('role_location'),240),
                        'after_country':_clean(result.get('country'),240),'at':timezone.now().isoformat(),
                    }
                else:
                    facts['source_location_reconciliation']={
                        'release':'0.11.5','fetched':False,'source_url':source_url[:500],
                        'before_role_location':stored_role,'error':_clean(fetched.get('error') or fetched.get('reason'),500),
                        'at':timezone.now().isoformat(),
                    }
            new_role=_clean(result.get('role_location'),240)
            prov=result.get('provenance') if isinstance(result.get('provenance'),dict) else {}
            prov_source=_clean(prov.get('source') or 'source_authoritative_role_location',80)
            # 0.11.5: rebuild canonical/filter locations from the current role display
            # before trusting persisted/structured arrays.  Older releases expanded broad
            # recruiter regions into long country lists, which left rows visible under
            # unrelated country filters (for example Albania) even after role_location
            # displayed a concise source value like Remote from US.
            role_first_locations=parse_location_items(new_role, source=prov_source, evidence=new_role) if new_role else []
            if role_first_locations:
                new_locations=normalize_location_items(role_first_locations)
            else:
                new_locations=normalize_location_items(result.get('locations') or result.get('country'))
            new_country=legacy_location_text(new_locations)
            fields=[]
            if hasattr(record,'locations') and new_locations != normalize_location_items(getattr(record,'locations',None)):
                record.locations=new_locations; fields.append('locations')
            if new_country and new_country != _clean(record.country,120):
                record.country=new_country; fields.append('country')
            elif not new_country and suspect and record.country:
                record.country=''; fields.append('country'); stats['opportunities_cleared']+=1
            if new_role and new_role != _clean(record.role_location,240):
                record.role_location=new_role; fields.append('role_location')
            facts['country_provenance']=result.get('provenance') or {}
            record.extracted_facts=facts; fields.append('extracted_facts')
            if fields:
                record.save(update_fields=list(dict.fromkeys(fields+['updated_at']))); stats['opportunities_updated']+=1
        except Exception:
            stats['errors']+=1
        if progress:
            try: progress(done,total,stats)
            except Exception: pass

    for record in CompanyLead.objects.order_by('pk').iterator(chunk_size=100):
        stats['hidden_leads_checked']+=1; done+=1
        try:
            country,evidence,source=company_hq_country_from_intel(record.company_intel)
            if not country and fetch_pages and (record.target_url or record.source_url or record.search_url):
                stats['page_fetches']+=1
                fetched=fetch_target(record.target_url or record.source_url or record.search_url,'',record.evidence or '',timeout=8)
                if fetched.get('ok'):
                    country,evidence,source=company_hq_country_from_text(fetched.get('text') or '')
            items=parse_location_items(country, source=source or 'country', evidence=evidence or country) if country else parse_location_items(record.country, source='country')
            new_country=legacy_location_text(items)
            fields=[]
            if hasattr(record,'locations') and normalize_location_items(record.locations) != normalize_location_items(items):
                record.locations=normalize_location_items(items); fields.append('locations')
            if new_country and new_country != _clean(record.country,120):
                record.country=new_country; fields.append('country')
            if fields:
                record.save(update_fields=list(dict.fromkeys(fields+['updated_at']))); stats['hidden_leads_updated']+=1
        except Exception:
            stats['errors']+=1
        if progress:
            try: progress(done,total,stats)
            except Exception: pass

    for record in Contact.objects.order_by('pk').iterator(chunk_size=100):
        stats['contacts_checked']+=1; done+=1
        try:
            country,evidence,source=company_hq_country_from_intel(record.company_intel)
            if not country and fetch_pages and record.source_url:
                stats['page_fetches']+=1
                fetched=fetch_target(record.source_url,record.company,record.notes or '',timeout=8)
                if fetched.get('ok'):
                    country,evidence,source=company_hq_country_from_text(fetched.get('text') or '')
            items=parse_location_items(country, source=source or 'company_country', evidence=evidence or country) if country else parse_location_items(record.company_country, source='company_country')
            new_country=legacy_location_text(items)
            fields=[]
            if hasattr(record,'company_locations') and normalize_location_items(record.company_locations) != normalize_location_items(items):
                record.company_locations=normalize_location_items(items); fields.append('company_locations')
            if new_country and new_country != _clean(record.company_country,120):
                record.company_country=new_country; fields.append('company_country')
            if fields:
                record.save(update_fields=fields); stats['contacts_updated']+=1
        except Exception:
            stats['errors']+=1
        if progress:
            try: progress(done,total,stats)
            except Exception: pass
    return stats
