from __future__ import annotations

import json
import re
from datetime import datetime, timezone as dt_timezone, timedelta

from django.utils import timezone

from portal.models import OpportunityEvidence, PortalSettings
from .pagefetch import fetch_target
from .content_quality import explicit_post_date_signal


def _parse_public_date(value):
    """Parse an AI/HTTP supplied date without trying to recognize page prose ourselves."""
    if not value:
        return None
    raw=str(value).strip()
    for candidate in (raw, raw.replace('Z','+00:00')):
        try:
            dt=datetime.fromisoformat(candidate)
            return dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)
        except Exception:
            pass
    try:
        from email.utils import parsedate_to_datetime
        dt=parsedate_to_datetime(raw)
        if dt:
            return dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)
    except Exception:
        pass
    return None


def _age_range_label(days):
    """Human review buckets rather than mathematical threshold notation.

    Beyond roughly six months a public posting date is usually too old or uncertain to
    present as a precise age, so ScoutBox deliberately switches to Likely Old.
    """
    if days is None:
        return 'Age unknown'
    try:
        days=max(0,int(days))
    except Exception:
        return 'Age unknown'
    if days < 3: return '< 3 days'
    if days < 7: return '< 1 week'
    if days < 14: return '~ 1 week'
    if days < 22: return '~2 weeks'
    if days < 46: return '~1 month'
    if days < 76: return '~2 months'
    if days < 107: return '~3 months'
    if days < 137: return '~4 months'
    if days < 168: return '~5 months'
    if days < 199: return '~6 months'
    return 'Likely Old'



def post_age_label_for_days(days):
    """Public canonical Post Age bucket helper used by ingestion, repair and UI."""
    return _age_range_label(days)


def _near_today(value, window_days=1):
    """True when a researched date is today or within the nearby-day ambiguity window."""
    if not value:
        return False
    try:
        local_day=timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    except Exception:
        local_day=value.date()
    return abs((local_day-timezone.localdate()).days) <= int(window_days)


def _page_date_is_explicit(signal):
    """Only an item/page statement of its posted/published date counts as explicit."""
    return bool(
        signal
        and signal.get('source') in {'Page content','Forum post'}
        and str(signal.get('meaning') or '').strip().lower() in {'posted','published'}
    )


def _displayable_best_date(value, explicit=False):
    """Suppress near-today best-date guesses unless backed by an explicit item statement."""
    if not value:
        return None
    if _near_today(value,1) and not explicit:
        return None
    return value


def _cloud_date_is_update_proxy(result):
    """Detect Cloud results that accidentally promoted document-update metadata to Post Age."""
    if not isinstance(result,dict):
        return False
    parts=[str(result.get('post_age_reason') or ''),str(result.get('evidence') or '')]
    for item in (result.get('post_age_evidence') or [])[:5]:
        if isinstance(item,dict):
            parts.extend([str(item.get('source') or item.get('label') or ''),str(item.get('reason') or item.get('note') or '')])
    text=' '.join(parts).casefold()
    return bool(re.search(
        r'\b(?:item|page|document|content)\s+(?:update|updated|modified)\s+date\b|'
        r'\blast[- ]modified\b|\blast updated\b|\b(?:page|document|content) updated\b|'
        r'\b(?:updated|modified) timestamp\b',
        text,
    ))


def _llm_page_date(text, final_url='', title=''):
    """Ask the configured model to identify the posting/publication date from cleaned page text.

    The model receives the already-cleaned main/article/job text rather than raw HTML.  No
    site-specific date regexes are used here: wording and locale interpretation are delegated
    to the model, while HTTP Last-Modified remains an independent low-confidence signal.
    """
    text=str(text or '').strip()
    if not text:
        return None
    try:
        from .ai import generate, route_for_stage
        if not route_for_stage('freshness'):
            return None
        today=timezone.localdate().isoformat()
        prompt=(
            'Read the cleaned text from one job, project, or opportunity page and identify when this specific item was posted or published. '
            'Prioritize an explicit posting/publication date and visible item-age phrases such as "4 months ago", "2 weeks ago", or "posted 6 days ago" that clearly belong to this job. '
            f'Today is {today}; when the item gives a relative age, convert that relative age to an approximate ISO date using today as the reference. '
            'Ignore cookie notices, navigation, footer dates, site-wide dates, application closing dates, recommended/related jobs, courses, and dates belonging to other items. '
            'An update/modified date is NOT a posting date. Never substitute an item/page "updated", "last updated", or modified timestamp for the posting date. '
            'If the only date you can find is an update/modified date, return that date with meaning=updated for audit, but do not claim it is the posting date. '
            'Do not guess from unrelated historical dates. Return JSON only with keys date, meaning, evidence, confidence. '
            'date must be ISO-8601 (YYYY-MM-DD or a full ISO timestamp), or null when no reliable item date is present. '
            'meaning must be posted, published, updated, or unknown. evidence should briefly describe the exact page phrase that supports the answer. confidence is 0-100.\n\n'
            f'Page title: {title[:300]}\nURL: {final_url[:1000]}\n\nCLEANED PAGE TEXT:\n{text[:30000]}'
        )
        raw=str(generate(prompt,stage='freshness',timeout=75) or '').strip()
        fenced=re.search(r'```(?:json)?\s*(.*?)```',raw,re.S|re.I)
        payload=(fenced.group(1).strip() if fenced else raw)
        a=payload.find('{'); b=payload.rfind('}')
        if a < 0 or b <= a:
            return None
        row=json.loads(payload[a:b+1])
        dt=_parse_public_date(row.get('date'))
        if not dt:
            return None
        now=timezone.now()
        if dt > now + timedelta(days=1):
            return None
        meaning=str(row.get('meaning') or 'unknown').strip().lower()
        try:
            confidence=max(25,min(98,int(row.get('confidence') or 70)))
        except Exception:
            confidence=70
        if meaning=='updated':
            confidence=min(confidence,62)
        elif meaning not in ('posted','published'):
            confidence=min(confidence,50)
        return {
            'label':'Page content · '+({'posted':'posted date','published':'publication date','updated':'item update date'}.get(meaning,'item date')),
            'date':dt,
            'confidence':confidence,
            'source':'Page content',
            'url':final_url,
            'note':str(row.get('evidence') or '')[:500],
            'meaning':meaning,
        }
    except Exception:
        return None


def _http_last_modified(headers, final_url=''):
    """Return a cautious HTTP Last-Modified signal, ignoring implausible/dynamic values."""
    value=(headers or {}).get('last_modified') or ''
    dt=_parse_public_date(value)
    if not dt:
        return None
    now=timezone.now()
    # Very old sentinel values (for example 1980) and future clocks are not evidence.
    if dt.year < 1995 or dt > now + timedelta(days=1):
        return None
    # Many dynamic servers set Last-Modified to approximately request time.  That does not
    # prove the opportunity was posted today, so omit unusually recent header values.
    if now-dt < timedelta(hours=24):
        return None
    return {
        'label':'HTTP Last-Modified',
        'date':dt,
        'confidence':42,
        'source':'HTTP header',
        'url':final_url,
        'note':'Server Last-Modified header; used only as a cautious supporting date.',
        'meaning':'modified',
    }


def _retained_board_post_signal(opportunity):
    """Return an explicit posting date retained from the original third-party board."""
    try:
        facts=opportunity.extracted_facts if isinstance(opportunity.extracted_facts,dict) else {}
        evidence=facts.get('original_job_board_evidence') if isinstance(facts.get('original_job_board_evidence'),dict) else {}
        dt=_parse_public_date(evidence.get('posted_date'))
        if not dt or dt > timezone.now()+timedelta(days=1):
            return None
        return {
            'label':'Original job board · posted date', 'date':dt,
            'confidence':max(90,min(98,int(evidence.get('posted_date_confidence') or 95))),
            'source':'Page content', 'url':str(evidence.get('url') or facts.get('original_job_board_url') or '')[:1000],
            'note':str(evidence.get('posted_date_note') or 'Explicit posted date retained before employer/ATS URL recovery.')[:500],
            'meaning':'posted',
        }
    except Exception:
        return None



def _forum_post_signal(opportunity):
    """Return the opportunity-bearing forum post timestamp when ScoutBox has it.

    Forum thread last-activity timestamps are intentionally not used here. The date must
    come from the specific post/candidate that triggered the opportunity, unless later
    Cloud/page evidence establishes a stronger explicit posting date.
    """
    try:
        facts=opportunity.extracted_facts if isinstance(opportunity.extracted_facts,dict) else {}
        forum=facts.get('forum') if isinstance(facts.get('forum'),dict) else {}
        dt=_parse_public_date(forum.get('post_date') or (facts.get('acquisition') or {}).get('published_at'))
        if not dt or dt > timezone.now()+timedelta(days=1):
            return None
        return {
            'label':'Forum post date', 'date':dt, 'confidence':96,
            'source':'Forum post', 'url':str(forum.get('url') or opportunity.target_url or opportunity.url or '')[:1000],
            'note':'Specific opportunity-bearing forum post timestamp; thread bumps/last activity are ignored.',
            'meaning':'posted',
        }
    except Exception:
        return None

def _collect_page_age_evidence(url, fallback_title='', fallback_text=''):
    page=fetch_target(url,fallback_title=fallback_title,fallback_text=fallback_text,timeout=22)
    final_url=page.get('target_url') or url
    fetch_note=(f"Fetched {final_url} (HTTP {page.get('http_status')})." if page.get('ok') else f"Page fetch failed: {page.get('error') or 'unknown error'}")
    signals=[]
    if page.get('ok'):
        page_signal=explicit_post_date_signal(
            page.get('text') or '', schema_date=page.get('jobposting_date_posted') or '', final_url=final_url
        )
        if page_signal:
            signals.append(page_signal)
        else:
            page_signal=_llm_page_date(page.get('text') or '',final_url,page.get('title') or fallback_title)
            if page_signal:
                signals.append(page_signal)
        header_signal=_http_last_modified(page.get('response_headers') or {},final_url)
        if header_signal:
            signals.append(header_signal)
    return signals,final_url,fetch_note,page


def _decide(signals):
    now=timezone.now()
    page=[s for s in signals if s.get('source') in {'Page content','Forum post'}]
    # A page/item update timestamp and an HTTP Last-Modified header describe document
    # maintenance, not when the role was posted. Keep them as audit/supporting evidence,
    # but never let them create or widen the displayed Post Age.
    posted_page=[s for s in page if str(s.get('meaning') or '').strip().lower() in {'posted','published'}]
    update_page=[s for s in page if str(s.get('meaning') or '').strip().lower() not in {'posted','published'}]
    headers=[s for s in signals if s.get('source')=='HTTP header']
    exact=max(posted_page,key=lambda x:x.get('confidence',0)) if posted_page else None
    if not exact:
        reason='No reliable posting/publication date was found.'
        if update_page:
            reason+=' Page update dates were retained as audit evidence but ignored for Post Age.'
        if headers:
            reason+=' HTTP Last-Modified was retained as supporting evidence but ignored for Post Age.'
        return {'exact':None,'label':'?','confidence':0,'age_days':None,'range_days':None,'range_signals':[],'reason':reason}

    confidence=int(exact.get('confidence') or 0)
    range_signals=[exact]
    reason='Best available evidence: '+str(exact.get('label') or 'posting date')+'.'
    if headers:
        h=headers[0]
        gap=abs((exact['date']-h['date']).days)
        if gap <= 31:
            confidence=min(98,max(confidence,82)+4)
            reason+=' HTTP Last-Modified is broadly consistent, but does not determine the posting age.'
        else:
            reason+=f' HTTP Last-Modified differs by about {gap} days and is ignored for posting age.'
    if update_page:
        reason+=' Page update-date evidence is ignored because an update is not a posting date.'

    exact_days=max(0,(now-exact['date']).days)
    return {
        'exact':exact,
        'label':_age_range_label(exact_days),
        'confidence':max(0,min(100,confidence)),
        'age_days':exact_days,
        'range_days':exact_days,
        'range_signals':range_signals,
        'reason':reason,
    }


def apply_cloud_post_age(opportunity, result):
    """Persist grounded Cloud Web posting-age evidence without invoking local AI.

    A near-today date (today or +/- one calendar day) is intentionally not exposed as
    the UI's "Best date" unless the Cloud verifier says the employer/ATS item itself
    explicitly states that date.  The researched value remains in evidence for audit.
    """
    raw_date=result.get('posted_date') or result.get('published_at')
    posted=_parse_public_date(raw_date)
    method=str(result.get('post_age_method') or ('explicit' if result.get('posted_date_explicit') else 'unknown')).strip().lower()
    retained_board=_retained_board_post_signal(opportunity)
    forum_post=_forum_post_signal(opportunity)
    # Prefer a specific forum post timestamp over unknown/inferred/guess Cloud age.
    if forum_post and (not posted or method in {'unknown','guess','inferred'}):
        posted=forum_post['date']; raw_date=posted.isoformat(); method='explicit'
        result=dict(result); result['posted_date_explicit']=True; result['age_days']=max(0,(timezone.now()-posted).days)
        result['post_age_reason']=('Forum source supplied the specific opportunity-bearing post date. '+str(result.get('post_age_reason') or '')).strip()
    # Prefer an explicit retained board date over an unknown/inferred/guess Cloud age.
    if retained_board and (not posted or method in {'unknown','guess','inferred'}):
        posted=retained_board['date']; raw_date=posted.isoformat(); method='explicit'
        result=dict(result); result['posted_date_explicit']=True; result['age_days']=max(0,(timezone.now()-posted).days)
        result['post_age_reason']=('Original job-board page explicitly stated the posting date. '+str(result.get('post_age_reason') or '')).strip()
    ignored_update_proxy=bool(posted and _cloud_date_is_update_proxy(result))
    if ignored_update_proxy:
        # Preserve the original model payload in AI request/audit logs, but do not persist a
        # document-maintenance timestamp as the job's posting date.
        posted=None
        raw_date=None
        method='unknown'
        result=dict(result)
        result['age_days']=None
    # Independent ScoutBox evidence: retain a cautious HTTP Last-Modified signal from the
    # directly fetched opportunity page. This is supporting evidence only and never an
    # archive.org API probe. Cloud Web may separately research archive.org in its prompt.
    http_signal=None
    try:
        page=fetch_target(opportunity.target_url or opportunity.url,opportunity.title,opportunity.description or opportunity.raw_search_snippet,timeout=15)
        if page.get('ok'):
            http_signal=_http_last_modified(page.get('response_headers') or {},page.get('target_url') or opportunity.url)
    except Exception:
        http_signal=None
    # HTTP Last-Modified is document-maintenance evidence, not a posting date. It is
    # retained below for audit but must never manufacture a Post Age when Cloud research
    # could not find one.
    explicit_raw=result.get('posted_date_explicit',False)
    explicit=(explicit_raw is True or str(explicit_raw).strip().lower() in {'1','true','yes','explicit'})
    age_days=result.get('age_days')
    try:
        age_days=max(0,int(age_days)) if age_days not in (None,'') else None
    except Exception:
        age_days=None
    if age_days is None and posted:
        age_days=max(0,(timezone.now()-posted).days)
    confidence=max(0,min(100,int(result.get('post_age_confidence') or result.get('confidence') or result.get('remote_confidence') or (70 if posted else 0))))
    if method=='guess': confidence=min(confidence,45)
    elif method=='inferred': confidence=min(confidence,68)
    label=_age_range_label(age_days)
    post_age_class=str(result.get('post_age_class') or '').strip().lower()
    try:
        evergreen_conf=max(0,min(100,int(result.get('evergreen_confidence') or 0)))
    except Exception:
        evergreen_conf=0
    evergreen=(post_age_class=='evergreen' and evergreen_conf>=60 and str(result.get('current_status') or '').strip().lower() not in {'closed','expired','filled','removed','inactive'})
    evergreen_reason=str(result.get('evergreen_reason') or '').strip()[:1200]
    if evergreen:
        label='Evergreen'
        confidence=max(confidence,evergreen_conf)
    if age_days is None and not evergreen:
        confidence=0
    display_date=_displayable_best_date(posted,explicit=explicit)
    suppressed=bool(posted and not display_date)

    OpportunityEvidence.objects.filter(opportunity=opportunity,kind__in=['cloud_posted_date','cloud_age_support']).delete()
    if posted:
        OpportunityEvidence.objects.create(
            opportunity=opportunity, kind='cloud_posted_date', label='Cloud Web researched posting date',
            value=posted.isoformat(), source_url=(opportunity.target_url or opportunity.url or ''),
            confidence=confidence,
            metadata={
                'note':str(result.get('post_age_reason') or result.get('evidence') or '')[:1200],
                'used_for_post_age':True,
                'provider':str(result.get('cloud_provider') or '')[:80],
                'posted_date_explicit':explicit,
                'post_age_method':method,
                'best_date_suppressed':suppressed,
                'post_age_class':('evergreen' if evergreen else post_age_class),
                'evergreen_confidence':evergreen_conf,
                'evergreen_reason':evergreen_reason,
            },
        )
    # Keep a short, human-reviewable set of corroborating dates returned by Cloud research.
    # These can include ordinary web/index/ATS/archive.org evidence, but ScoutBox never probes
    # archive.org directly. Each support date remains evidence rather than becoming the posting date.
    seen_support=set()
    for item in (result.get('post_age_evidence') or [])[:5]:
        if not isinstance(item,dict):
            continue
        value=str(item.get('date') or item.get('value') or '').strip()[:120]
        src=str(item.get('url') or item.get('source_url') or '').strip()[:1000]
        label=str(item.get('source') or item.get('label') or 'Cloud corroborating date').strip()[:200]
        reason=str(item.get('reason') or item.get('note') or '').strip()[:1000]
        key=(value,src,label.casefold())
        if not value or key in seen_support:
            continue
        seen_support.add(key)
        try:
            conf=max(0,min(100,int(item.get('confidence') or 45)))
        except Exception:
            conf=45
        OpportunityEvidence.objects.create(
            opportunity=opportunity, kind='cloud_age_support', label=label, value=value,
            source_url=src, confidence=conf,
            metadata={'note':reason,'used_for_post_age':False,'provider':str(result.get('cloud_provider') or '')[:80]},
        )
    opportunity.estimated_first_seen=display_date
    opportunity.declared_posted_at=(posted if explicit else None)
    opportunity.freshness_label=label
    opportunity.freshness_confidence=confidence
    facts=dict(opportunity.extracted_facts or {})
    reason=str(result.get('post_age_reason') or result.get('evidence') or ('Grounded Cloud Web posting-age evidence.' if age_days is not None else 'Cloud Web could not verify a posting date.'))[:1600]
    if ignored_update_proxy:
        reason=('Ignored a page/item update or modified timestamp because it does not establish when the role was posted. '+reason)[:1600]
    if evergreen:
        reason=(reason+' Evergreen: '+(evergreen_reason or 'Cloud Web evidence indicates this is a long-running or continuously open role; it may still be applied to.'))[:1600]
    if suppressed:
        reason=(reason+' Best date hidden because the researched date is within +/-1 day of today and is not explicitly stated on the item page.')[:1600]
    facts['post_age']={
        'label':label,'confidence':confidence,
        'exact_date':display_date.isoformat() if display_date else '',
        'researched_date':posted.isoformat() if posted else '',
        'exact_source':'Cloud Web research' if display_date else '',
        'posted_date_explicit':explicit,
        'best_date_suppressed':suppressed,
        'age_days':age_days,'range_days':age_days,
        'post_age_class':('evergreen' if evergreen else post_age_class),
        'evergreen':evergreen,
        'evergreen_confidence':evergreen_conf,
        'evergreen_reason':evergreen_reason,
        'reason':reason,
        'resolved_url':opportunity.target_url or opportunity.url or '',
    }
    if http_signal:
        OpportunityEvidence.objects.update_or_create(
            opportunity=opportunity,kind='http_last_modified',label='HTTP Last-Modified',
            defaults={'value':http_signal['date'].isoformat(),'source_url':http_signal.get('url') or opportunity.url,'confidence':http_signal.get('confidence',42),'metadata':{'note':http_signal.get('note',''),'used_for_post_age':False}})
    facts['post_age']['method']=method
    facts['post_age']['cloud_guess']=bool(method=='guess')
    opportunity.extracted_facts=facts
    opportunity.save(update_fields=['estimated_first_seen','declared_posted_at','freshness_label','freshness_confidence','extracted_facts','updated_at'])
    return {'label':label,'confidence':confidence,'earliest':display_date,'signals':[],'disabled':False,'age_days':age_days,'reason':reason}


def recompute(opportunity):
    cfg=PortalSettings.objects.get_or_create(pk=1)[0]
    if not cfg.feature_age_estimation:
        opportunity.freshness_label='?'; opportunity.freshness_confidence=0; opportunity.estimated_first_seen=None
        facts=dict(opportunity.extracted_facts or {}); facts['post_age']={'label':'?','confidence':0,'exact_date':'','reason':'Post age estimation is disabled.'}; opportunity.extracted_facts=facts
        opportunity.save(update_fields=['freshness_label','freshness_confidence','estimated_first_seen','extracted_facts','updated_at'])
        return {'label':'?','confidence':0,'earliest':None,'signals':[],'disabled':True}

    url=(opportunity.target_url or opportunity.url or '').strip()
    signals,final_url,fetch_note,page=_collect_page_age_evidence(url,opportunity.title,opportunity.description or opportunity.raw_search_snippet)
    forum_post=_forum_post_signal(opportunity)
    if forum_post:
        signals.insert(0,forum_post)
    retained_board=_retained_board_post_signal(opportunity)
    if retained_board:
        signals.append(retained_board)
    decision=_decide(signals)
    exact=decision['exact']

    # Replace only evidence produced by this mechanism; historical portal/archive evidence
    # may remain in the database for audit but no longer controls Post Age.
    OpportunityEvidence.objects.filter(opportunity=opportunity,kind__in=['page_date_llm','http_last_modified','forum_post_date']).delete()
    for sig in signals:
        kind='forum_post_date' if sig.get('source')=='Forum post' else ('page_date_llm' if sig.get('source')=='Page content' else 'http_last_modified')
        OpportunityEvidence.objects.create(
            opportunity=opportunity,kind=kind,label=sig['label'],value=sig['date'].isoformat(),
            source_url=sig.get('url') or final_url,confidence=int(sig.get('confidence') or 0),
            metadata={'note':sig.get('note',''),'meaning':sig.get('meaning',''),'fetch':fetch_note,'used_for_post_age':sig in decision.get('range_signals',[])},
        )

    exact_date=exact['date'] if exact else None
    explicit_exact=_page_date_is_explicit(exact)
    display_date=_displayable_best_date(exact_date,explicit=explicit_exact)
    suppressed=bool(exact_date and not display_date)
    page_exact=next((s for s in signals if s.get('source')=='Page content' and exact and s is exact),None)
    opportunity.estimated_first_seen=display_date
    opportunity.declared_posted_at=(page_exact['date'] if page_exact and explicit_exact else None)
    opportunity.freshness_label=decision['label']
    opportunity.freshness_confidence=decision['confidence']
    facts=dict(opportunity.extracted_facts or {})
    facts['post_age']={
        'label':decision['label'],
        'confidence':decision['confidence'],
        'exact_date':display_date.isoformat() if display_date else '',
        'researched_date':exact_date.isoformat() if exact_date else '',
        'exact_source':exact.get('source','') if display_date and exact else '',
        'posted_date_explicit':explicit_exact,
        'best_date_suppressed':suppressed,
        'exact_meaning':exact.get('meaning','') if exact else '',
        'age_days':decision['age_days'],
        'range_days':decision['range_days'],
        'reason':(decision['reason'] + (' Best date hidden because the researched date is within +/-1 day of today and is not explicitly stated on the item page.' if suppressed else '')),
        'resolved_url':final_url,
        'fetch_note':fetch_note,
    }
    opportunity.extracted_facts=facts
    if final_url and final_url!=url:
        opportunity.target_url=final_url
    opportunity.save(update_fields=['estimated_first_seen','declared_posted_at','freshness_label','freshness_confidence','extracted_facts','target_url','updated_at'])
    return {'label':decision['label'],'confidence':decision['confidence'],'earliest':display_date,'signals':signals,'disabled':False,'age_days':decision['age_days'],'reason':facts['post_age']['reason']}


def analyze_url_age(url):
    """Non-persistent Post Age analysis for Performance Lab."""
    signals,final_url,fetch_note,page=_collect_page_age_evidence(url)
    decision=_decide(signals)
    exact=decision['exact']
    exact_date=exact['date'] if exact else None
    display_date=_displayable_best_date(exact_date,explicit=_page_date_is_explicit(exact))
    return {
        'url':url,
        'resolved_url':final_url,
        'label':decision['label'],
        'age_days':decision['age_days'],
        'estimated_date':display_date.isoformat() if display_date else None,
        'confidence':decision['confidence'],
        'reasoning':decision['reason'],
        'fetch_note':fetch_note,
        'signals':[{'label':s['label'],'date':s['date'].isoformat(),'confidence':s['confidence'],'note':s.get('note',''),'url':s.get('url','')} for s in signals],
    }


def opportunity_post_age_display_label(opportunity):
    """Return the canonical human Post Age label used by list/detail views.

    Exact retained evidence (age_days or a retained posting date) outranks a legacy
    stored bucket.  This prevents an older worker label such as ``~ 1 week`` from being
    displayed for a record whose retained evidence says age_days=0.
    """
    raw=str(getattr(opportunity,'freshness_label','') or '').strip()
    if raw in {'Evergreen Post','Ever-green','Evergreen'}:
        return 'Evergreen'

    try:
        confidence=int(getattr(opportunity,'freshness_confidence',0) or 0)
    except Exception:
        confidence=0

    facts=getattr(opportunity,'extracted_facts',{}) or {}
    post=facts.get('post_age') if isinstance(facts,dict) and isinstance(facts.get('post_age'),dict) else {}
    current_status=str(post.get('current_status') or facts.get('current_status') or '').strip().lower()
    evergreen_flag=(
        post.get('evergreen') is True or
        str(post.get('post_age_class') or '').strip().lower()=='evergreen' or
        str(post.get('class') or '').strip().lower()=='evergreen'
    )
    try:
        evergreen_conf=int(post.get('evergreen_confidence') or post.get('confidence') or confidence or 0)
    except Exception:
        evergreen_conf=confidence
    if confidence>0 and evergreen_flag and evergreen_conf>=60 and current_status not in {'closed','expired','filled','removed','inactive'}:
        return 'Evergreen'

    if confidence>0:
        # Prefer a retained exact date over a cached age_days counter so the bucket
        # naturally advances as time passes without depending on another worker write.
        # Evergreen classification is checked above because it is a qualitative post-age
        # value, not an age range; date recalc must not demote it to < 3 days/Likely Old.
        dt=(getattr(opportunity,'declared_posted_at',None) or
            _parse_public_date(post.get('exact_date')) or
            _parse_public_date(post.get('researched_date')) or
            getattr(opportunity,'estimated_first_seen',None))
        if dt:
            try:
                now=timezone.now()
                if timezone.is_naive(dt):
                    dt=timezone.make_aware(dt,timezone.get_current_timezone())
                return _age_range_label(max(0,(now-dt).days))
            except Exception:
                pass
        try:
            age_days=post.get('age_days')
            if age_days not in (None,''):
                return _age_range_label(max(0,int(age_days)))
        except Exception:
            pass

    allowed={'Evergreen','Evergreen Post','Ever-green','Likely Old','< 1 week','<3 days','< 3 days','~3 days','~ 3 days','~1 week','~ 1 week','~2 weeks','~2 weeks','~1 month','~2 months','~3 months','~4 months','~5 months','~6 months','Age unknown'}
    if raw in allowed:
        if raw in {'<3 days','< 3 days','~3 days','~ 3 days'}: return '< 3 days'
        if raw in {'~1 week','~ 1 week'}: return '~ 1 week'
        return raw
    if raw in {'Older / uncertain','Stale / uncertain','Old / uncertain','Uncertain / older','Likely old'}:
        return 'Likely Old'
    return 'Age unknown'


def opportunity_post_age_sort_days(opportunity):
    """Return a numeric Post Age key in days, or None when the list displays ``?``.

    This deliberately mirrors the Opportunity-list presentation contract: an age with
    no confidence is unknown even if an old retained date happens to exist. Unknown
    values must stay out of the numeric ordering so callers can keep them last in both
    newest-first and oldest-first sorts.
    """
    try:
        confidence=int(getattr(opportunity,'freshness_confidence',0) or 0)
    except Exception:
        confidence=0
    if confidence <= 0:
        return None

    facts=getattr(opportunity,'extracted_facts',{}) or {}
    post=facts.get('post_age') if isinstance(facts,dict) and isinstance(facts.get('post_age'),dict) else {}
    dt=(getattr(opportunity,'declared_posted_at',None) or
        _parse_public_date(post.get('exact_date')) or
        _parse_public_date(post.get('researched_date')) or
        getattr(opportunity,'estimated_first_seen',None))
    if dt:
        try:
            now=timezone.now()
            if timezone.is_naive(dt):
                dt=timezone.make_aware(dt,timezone.get_current_timezone())
            return max(0,(now-dt).days)
        except Exception:
            pass
    try:
        raw=post.get('age_days')
        if raw not in (None,''):
            return max(0,int(raw))
    except Exception:
        pass

    raw_label=str(getattr(opportunity,'freshness_label','') or '').strip()
    normalized={
        'Evergreen Post':'Evergreen','Ever-green':'Evergreen',
        'Older / uncertain':'Likely Old','Stale / uncertain':'Likely Old',
        'Old / uncertain':'Likely Old','Uncertain / older':'Likely Old','Likely old':'Likely Old',
    }.get(raw_label,raw_label)
    approximate={
        '< 1 week':3,'<3 days':1,'< 3 days':1,'~3 days':1,'~ 3 days':1,'~1 week':7,'~ 1 week':7,'~2 weeks':14,'~1 month':30,'~2 months':60,'~3 months':90,
        '~4 months':120,'~5 months':150,'~6 months':180,'Likely Old':365,'Evergreen':730,
    }
    return approximate.get(normalized)
