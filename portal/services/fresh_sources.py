"""Fresh/direct discovery adapters.

These adapters deliberately bypass general web-search indexes.  They retrieve the newest
published items from first-party/public job APIs, feeds, ATS posting endpoints and hiring
communities, then apply a cheap campaign relevance/freshness pre-filter before the normal
ScoutBox AI qualification pipeline sees a candidate.

The module is shared by Local AI Discovery and Cloud Web Discovery.  The discovery mode
only decides which AI evaluates the directly acquired candidate; it never changes how the
source itself is harvested.
"""
from __future__ import annotations

import concurrent.futures
import calendar
import hashlib
import html
import json
import os
import re
import threading
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone as dt_timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup
from django.core.cache import cache
from django.db import close_old_connections
from django.db.models import Count, Max, Q
from django.utils import timezone

from portal.models import Opportunity, CompanyLead, SearchProviderStat, SearchSource, UsageMetric
from .forum_sources import (
    FORUM_DIRECT_ADAPTER, build_forum_queries, forum_result_looks_promising,
    forum_search_url, forum_listing_urls, parse_forum_search_results,
)
from .source_domains import direct_endpoint_variants
from .platforms import is_plausible_company_name, company_from_ats_url


DIRECT_ADAPTERS = {
    'remoteok', 'remotive', 'himalayas', 'jobicy', 'wwr_rss',
    'hn_whoishiring', 'yc_jobs', 'lobsters_jobs', 'dev_hiring', 'indiehackers_jobs', 'reddit',
    'linkedin_job_library', 'glassdoor_jobs', 'wellfound_page',
    'greenhouse', 'lever', 'ashby', 'smartrecruiters', FORUM_DIRECT_ADAPTER,
}

# Public feeds have different sensible polling cadences.  This cache is intentionally
# shared across campaigns: raw source data is cached, while relevance filtering still runs
# independently for every campaign.
DEFAULT_CACHE_SECONDS = {
    'remoteok': 1800,
    'remotive': 3600,
    'himalayas': 86400,   # provider says the public data itself refreshes daily
    'jobicy': 3600,       # provider asks automated polling not exceed once/hour
    'wwr_rss': 3600,
    'hn_whoishiring': 1800,
    'yc_jobs': 1800,
    'lobsters_jobs': 1800,
    'dev_hiring': 1800,
    'indiehackers_jobs': 1800,
    'linkedin_job_library': 900,
    'glassdoor_jobs': 1800,
    'wellfound_page': 1800,
    'reddit': 1800,
    'greenhouse': 1800,
    'lever': 1800,
    'ashby': 1800,
    'smartrecruiters': 1800,
    FORUM_DIRECT_ADAPTER: 7200,
}

_ROLE_WORDS = re.compile(
    r'(?i)\b(?:principal|staff|senior|lead|junior|embedded|firmware|linux|kernel|rtos|fpga|systems?|platform|devops|security|technical|developer|engineer|architect|consultant|writer|researcher|scientist|programmer|administrator|specialist)\b'
)
_STOP = {
    'the','and','with','for','from','into','that','this','your','you','our','their','they','are','job','jobs','role','roles','work','working','remote','engineer','engineering','developer','development','software','technical','senior','lead','staff','principal','specialist','consultant','manager','full','time','based','looking','hiring','wanted','position','positions','opportunity','opportunities'
}
_NEGATIVE_REMOTE = re.compile(r'(?i)\b(?:on[ -]?site only|onsite only|office only|no remote|must be in the office|not remote)\b')
_REMOTE_HINT = re.compile(r'(?i)\b(?:remote|distributed|work from home|wfh|anywhere|worldwide|home[- ]based)\b')
_HIRING_HINT = re.compile(r'(?i)\b(?:we(?:\'re| are) hiring|hiring|job opening|open role|vacanc(?:y|ies)|apply|join (?:our|the) team|seeking|looking for)\b')


def _text(value):
    if value is None:
        return ''
    if isinstance(value, (list, tuple, set)):
        return ' '.join(_text(x) for x in value if x is not None)
    if isinstance(value, dict):
        return ' '.join(_text(x) for x in value.values() if x is not None)
    return ' '.join(str(value).replace('\xa0',' ').split())


def _plain(value, limit=12000):
    raw=str(value or '')
    if '<' in raw and '>' in raw:
        raw=BeautifulSoup(raw,'html.parser').get_text(' ',strip=True)
    return _text(html.unescape(raw))[:limit]


def _parse_date(value):
    if value in (None,''):
        return None
    if isinstance(value,(int,float)):
        # APIs use both seconds and milliseconds.
        raw=float(value)
        if raw > 10_000_000_000:
            raw/=1000.0
        try: return datetime.fromtimestamp(raw,tz=dt_timezone.utc)
        except Exception: return None
    text=str(value).strip()
    if not text: return None
    try:
        dt=datetime.fromisoformat(text.replace('Z','+00:00'))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=dt_timezone.utc)
        return dt
    except Exception:
        pass
    try:
        dt=parsedate_to_datetime(text)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=dt_timezone.utc)
        return dt
    except Exception:
        return None


def _iso(value):
    dt=_parse_date(value)
    return dt.isoformat() if dt else ''


def _campaign_terms(campaign, search_profile=None):
    weighted=[]
    def add(raw, weight):
        for piece in re.split(r'[,;|\n/]+',str(raw or '')):
            piece=_text(piece)
            if not piece: continue
            weighted.append((piece,weight))
            for token in re.findall(r'[A-Za-z0-9+#.]{3,}',piece):
                low=token.casefold().strip('.')
                if low and low not in _STOP:
                    weighted.append((token, max(1,weight-1)))
    add(getattr(campaign,'role_families',''),6)
    add(getattr(campaign,'technologies',''),5)
    add(getattr(campaign,'extra_text',''),2)
    for idx,row in enumerate((search_profile or {}).get('skills',[]) or []):
        if isinstance(row,dict):
            sources=row.get('sources') if isinstance(row.get('sources'),dict) else {}
            weight=4 if idx<25 else (3 if sources.get('cv') or str(row.get('category') or '').casefold()=='cv-specific' else 2)
            add(row.get('term',''),weight)
            if sources.get('cv') or str(row.get('category') or '').casefold()=='cv-specific':
                for variant in row.get('matched_variants') or []:
                    add(variant,max(2,weight-1))
        else:
            add(row,4 if idx<25 else 2)
    seen={}; out=[]
    for term,weight in weighted:
        key=term.casefold()
        if len(key)<3 or key in seen: continue
        seen[key]=weight; out.append((term,weight))
    return out[:160]


def _query_phrase(campaign, search_profile=None):
    variants=_direct_query_variants(campaign,search_profile,max_queries=1) if '_direct_query_variants' in globals() else []
    if variants:
        return variants[0]
    # Prefer a role family, then a concrete technology.  APIs that support a q/tag
    # parameter should receive one concise query rather than a large boolean expression.
    for raw in (getattr(campaign,'role_families',''), getattr(campaign,'technologies','')):
        for piece in re.split(r'[,;|\n]+',str(raw or '')):
            piece=_text(piece)
            if 3 <= len(piece) <= 70:
                return piece
    for term,_ in _campaign_terms(campaign,search_profile):
        if 3 <= len(term) <= 70: return term
    return ''


def _split_config_terms(raw, *, max_len=80):
    out=[]
    if raw is None:
        return out
    if isinstance(raw,(list,tuple,set)):
        values=raw
    else:
        values=re.split(r'[,;|\n]+',str(raw or ''))
    seen=set()
    for value in values:
        text=_text(value).strip(' ,;:-')
        if not text or len(text)>max_len:
            continue
        key=text.casefold()
        if key in _STOP or key in seen:
            continue
        seen.add(key); out.append(text)
    return out


def _append_unique(target, value, *, max_len=90):
    text=_text(value).strip(' ,;:-')
    if not text or len(text)>max_len:
        return
    low=text.casefold()
    if low in {x.casefold() for x in target}:
        return
    target.append(text)


def _rotated(values, campaign=None, adapter='', limit=None):
    values=[v for v in values if _text(v)]
    if not values:
        return []
    try:
        bucket=timezone.now().strftime('%Y%m%d%H')
        seed=sum(ord(ch) for ch in f'{getattr(campaign,"pk","")}:{adapter}:{bucket}')
        offset=seed % len(values)
        values=values[offset:]+values[:offset]
    except Exception:
        pass
    return values[:limit] if limit else values


def _direct_query_variants(campaign, search_profile=None, *, adapter='', max_queries=5, include_intent=False):
    """Build rotated, campaign-aware direct-source search terms.

    Direct adapters should not repeatedly ask their APIs for one static role phrase.
    This planner mixes role families, technologies, engagement terms and CV-derived
    skills into compact queries, then rotates them hourly so repeated runs cover the
    full candidate profile instead of getting stuck on the highest-scoring terms.
    """
    role_terms=[]; tech_terms=[]; engagement_terms=[]; extra_terms=[]
    skill_terms=[]; cv_terms=[]; preferred_terms=[]
    steering=(search_profile or {}).get('campaign_steering') or {}
    for raw in steering.get('roles') or []:
        _append_unique(role_terms,raw,max_len=70)
    for raw in steering.get('technologies') or []:
        _append_unique(tech_terms,raw,max_len=70)
    for raw in _split_config_terms(getattr(campaign,'role_families',''),max_len=70):
        _append_unique(role_terms,raw,max_len=70)
    for raw in _split_config_terms(getattr(campaign,'technologies',''),max_len=70):
        _append_unique(tech_terms,raw,max_len=70)
    for raw in _split_config_terms(getattr(campaign,'engagement_types',''),max_len=50):
        _append_unique(engagement_terms,raw,max_len=50)
    for raw in _split_config_terms(getattr(campaign,'extra_text',''),max_len=60):
        _append_unique(extra_terms,raw,max_len=60)

    # Use the entire scored profile, not only the first few skills.  CV-specific
    # technologies are deliberately separated and rotated so lower-frequency terms
    # such as .NET, C#, VoIP or Asterisk receive search coverage over time.
    for row in (search_profile or {}).get('skills',[]) or []:
        if isinstance(row,dict):
            term=row.get('term') or row.get('query') or ''
            sources=row.get('sources') if isinstance(row.get('sources'),dict) else {}
            category=str(row.get('category') or '').casefold()
            score=float(row.get('score') or 0)
            target=cv_terms if sources.get('cv') or category=='cv-specific' else (preferred_terms if score>=8 else skill_terms)
            _append_unique(target,term,max_len=70)
            for variant in row.get('matched_variants') or []:
                _append_unique(target,variant,max_len=70)
        else:
            _append_unique(skill_terms,row,max_len=70)

    for term,_weight in _campaign_terms(campaign,search_profile):
        if _ROLE_WORDS.search(str(term)):
            _append_unique(role_terms,term,max_len=60)
        else:
            _append_unique(tech_terms,term,max_len=60)

    fallback_focus=[]
    focus=[]
    # Campaign terms remain first, but CV terms are rotated as a whole before
    # generic fallbacks so direct adapters do not search only QEMU/virtualization.
    cv_rotated=_rotated(cv_terms,campaign,adapter+':cv-tech',limit=max(12,min(len(cv_terms) or 0, max_queries*8)))
    preferred_rotated=_rotated(preferred_terms,campaign,adapter+':preferred-tech',limit=max(10,min(len(preferred_terms) or 0, max_queries*6)))
    skill_rotated=_rotated(skill_terms,campaign,adapter+':profile-tech',limit=max(12,min(len(skill_terms) or 0, max_queries*8)))
    interleaved=[]
    for idx in range(max([len(tech_terms),len(cv_rotated),len(preferred_rotated),len(skill_rotated),len(extra_terms),1])):
        for group in (tech_terms,cv_rotated,preferred_rotated,skill_rotated,extra_terms):
            if idx < len(group):
                _append_unique(interleaved,group[idx],max_len=70)
    for group in (interleaved,fallback_focus):
        for term in group:
            _append_unique(focus,term,max_len=70)

    role_base=[]
    for term in role_terms:
        _append_unique(role_base,term,max_len=70)
    intents=[]
    for term in engagement_terms + ['remote','contract','contractor','consultant','freelance','part-time','paid project','hiring','open role']:
        _append_unique(intents,term,max_len=35)

    queries=[]
    community=adapter in {'reddit','hn_whoishiring','lobsters_jobs','dev_hiring','indiehackers_jobs'}
    # Concrete specialty-only queries first: most direct APIs search title/body and
    # return better recall for "Asterisk" or "SIP" than for one long role phrase.
    for tech in _rotated(focus,campaign,adapter+':focus',limit=max_queries*2):
        _append_unique(queries,tech,max_len=80)
        if len(queries)>=max_queries:
            return queries
    # Mix role families with specialties after specialty-only queries.
    for role in _rotated(role_base,campaign,adapter+':role',limit=4):
        for tech in _rotated(focus,campaign,adapter+':rolefocus',limit=max(5,max_queries)):
            _append_unique(queries,f'{role} {tech}',max_len=90)
            if len(queries)>=max_queries:
                return queries
    # Engagement-intent variants are especially useful for community sources.
    if include_intent or community:
        for tech in _rotated(focus,campaign,adapter+':intentfocus',limit=max(8,max_queries)):
            for intent in _rotated(intents,campaign,adapter+':intent',limit=5):
                _append_unique(queries,f'{tech} {intent}',max_len=90)
                if len(queries)>=max_queries:
                    return queries
    return queries[:max_queries]

def _direct_row_dedupe_key(row):
    row=row if isinstance(row,dict) else {}
    item_id=str(row.get('_direct_item_id') or '').strip().casefold()
    if item_id:
        adapter=str(row.get('_direct_adapter') or '').strip().casefold()
        board=str(row.get('_ats_board') or '').strip().casefold()
        return f'id:{adapter}:{board}:{item_id}'
    url=str(row.get('url') or '').strip().casefold().rstrip('/')
    return f'url:{url}' if url else ''


def _merge_rows_unique(existing, new_rows):
    # Direct endpoint/domain variants can return the same provider item on different
    # hostnames. Prefer the provider item id (scoped by adapter/board) over URL so those
    # variants converge to one candidate.
    seen={_direct_row_dedupe_key(row) for row in existing}
    seen.discard('')
    for row in new_rows or []:
        key=_direct_row_dedupe_key(row)
        if not key or key in seen:
            continue
        seen.add(key); existing.append(row)
    return existing


def _score_candidate(row, terms):
    title=_text(row.get('title')).casefold()
    blob=(title+' '+_text(row.get('company'))+' '+_text(row.get('snippet'))).casefold()
    score=0; hits=[]
    for term,weight in terms:
        key=term.casefold()
        if not key: continue
        if key in title:
            score+=weight*3; hits.append(term)
        elif key in blob:
            score+=weight; hits.append(term)
    if _ROLE_WORDS.search(title): score+=3
    if _HIRING_HINT.search(blob): score+=2
    if _REMOTE_HINT.search(blob): score+=2
    row['_fresh_prefilter_score']=score
    row['_matched_profile_terms']=list(dict.fromkeys(hits))[:12]
    return score


def _fresh_enough(row, campaign):
    published=_parse_date(row.get('published_at'))
    if not published:
        return True
    try: days=max(1,min(120,int(getattr(campaign,'recency_days',30) or 30)))
    except Exception: days=30
    return published >= timezone.now().astimezone(dt_timezone.utc)-timezone.timedelta(days=days)


def _keep_candidate(row, campaign, terms):
    url=str(row.get('url') or '').strip()
    title=_text(row.get('title'))
    if not url.startswith(('http://','https://')) or not title:
        return False
    blob=title+' '+_text(row.get('snippet'))+' '+_text(row.get('remote_text'))
    if _NEGATIVE_REMOTE.search(blob):
        return False
    if not _fresh_enough(row,campaign):
        return False
    if not terms:
        return True
    score=_score_candidate(row,terms)
    if row.get('_forum_source'):
        # Forum marketplace/listing browse rows are intentionally broad. Keep the cheap
        # prefilter light and let the normal LLM qualification decide final relevance.
        return score >= 2 or forum_result_looks_promising(row,campaign,None)
    # Role phrases are weighted heavily; a single concrete technology hit is also enough.
    return score >= 4


def _cache_key(url, params):
    packed=url+'?'+urllib.parse.urlencode(sorted((str(k),str(v)) for k,v in (params or {}).items()))
    return 'scoutbox:fresh:'+hashlib.sha256(packed.encode()).hexdigest()


def _network_metric(source, adapter, url, *, cached=False, ok=True, count=0, elapsed_ms=0, bytes_downloaded=0, error='', query=''):
    if not cached:
        try:
            stat,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate())
            stat.requests+=1
            if not ok: stat.errors+=1; stat.last_error=str(error or '')[:2000]
            stat.avg_latency_ms=int(((int(stat.avg_latency_ms or 0)*max(0,int(stat.requests or 1)-1))+int(elapsed_ms or 0))/max(1,int(stat.requests or 1)))
            stat.bytes_downloaded=int(stat.bytes_downloaded or 0)+max(0,int(bytes_downloaded or 0))
            stat.save(update_fields=['requests','errors','last_error','avg_latency_ms','bytes_downloaded'])
        except Exception:
            pass
    try:
        UsageMetric.objects.create(
            category='fresh_source',provider=getattr(source,'name',''),stage=adapter,
            requests=0 if cached else 1,pages=1 if ok else 0,errors=0 if ok else 1,
            latency_ms=max(0,int(elapsed_ms or 0)),bytes_downloaded=max(0,int(bytes_downloaded or 0)) if not cached else 0,
            metadata={'acquisition_path':'direct','adapter':adapter,'url':url[:1000],'query':str(query or '')[:500],'cached':bool(cached),'results':max(0,int(count or 0)),'error':str(error or '')[:500]},
        )
    except Exception:
        pass


def _adapter_result_metric(source, adapter, count, *, started_at=None, error='', selection_reason=''):
    """Record one user-facing Direct Search outcome for an adapter invocation.

    Individual HTTP metrics remain useful telemetry, but Search Activity should report
    the adapter's parsed result count rather than showing every successful HTTP request
    as "0 results".  Aggregate the network work performed by this invocation into this
    outcome row; cache-backed invocations legitimately have zero network requests.
    """
    count=max(0,int(count or 0))
    provider=getattr(source,'name','')
    try:
        stat,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate())
        stat.results=int(stat.results or 0)+count
        stat.save(update_fields=['results'])
    except Exception:
        pass
    network=[]
    try:
        q=UsageMetric.objects.filter(category='fresh_source',provider=provider,stage=adapter)
        if started_at is not None:
            q=q.filter(at__gte=started_at)
        network=list(q.order_by('at','pk')[:200])
    except Exception:
        network=[]
    requests=sum(max(0,int(x.requests or 0)) for x in network)
    bytes_downloaded=sum(max(0,int(x.bytes_downloaded or 0)) for x in network)
    latency_ms=sum(max(0,int(x.latency_ms or 0)) for x in network)
    urls=[]
    domains=[]
    queries=[]
    partial_errors=[]
    for metric in network:
        meta=metric.metadata if isinstance(metric.metadata,dict) else {}
        url=str(meta.get('url') or '').strip()
        if url and url not in urls: urls.append(url)
        if url:
            try:
                host=(urllib.parse.urlsplit(url).hostname or '').casefold().removeprefix('www.')
            except Exception:
                host=''
            if host and host not in domains: domains.append(host)
        qtext=str(meta.get('query') or '').strip()
        if qtext and qtext not in queries: queries.append(qtext)
        err=str(meta.get('error') or '').strip()
        if err and err not in partial_errors: partial_errors.append(err)
    error_text=str(error or '').strip() or ('; '.join(partial_errors[:3]) if count<=0 else '')
    try:
        UsageMetric.objects.create(
            category='fresh_source_result',provider=provider,stage=adapter,
            requests=requests,pages=count,errors=1 if error_text and count<=0 else 0,
            latency_ms=latency_ms,bytes_downloaded=bytes_downloaded,
            metadata={
                'acquisition_path':('Forum source' if adapter==FORUM_DIRECT_ADAPTER else 'direct'),
                'source_category':('forum' if adapter==FORUM_DIRECT_ADAPTER else 'direct'),
                'forum': bool(adapter==FORUM_DIRECT_ADAPTER),
                'adapter':adapter,'results':count,'selection_reason':str(selection_reason or '')[:80],
                'query':('; '.join(queries[:6]))[:1000],
                'url':(urls[0] if urls else '')[:1000],
                'urls':urls[:12],
                'domains_touched':domains,
                'cached':bool(network) and requests==0,
                'error':error_text[:500],
            },
        )
    except Exception:
        pass


def _adapter_exception_metric(source, adapter, error):
    """Record adapter/parser exceptions that occur outside a network request helper."""
    try:
        stat,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate())
        stat.errors=int(stat.errors or 0)+1; stat.last_error=str(error or '')[:2000]
        stat.save(update_fields=['errors','last_error'])
    except Exception:
        pass
    try:
        UsageMetric.objects.create(
            category='fresh_source',provider=getattr(source,'name',''),stage=adapter,
            requests=0,pages=0,errors=1,metadata={'acquisition_path':('Forum source' if adapter==FORUM_DIRECT_ADAPTER else 'direct'),'source_category':('forum' if adapter==FORUM_DIRECT_ADAPTER else 'direct'),'forum':bool(adapter==FORUM_DIRECT_ADAPTER),'adapter':adapter,'error':str(error or '')[:500]},
        )
    except Exception:
        pass


def _adapter_configured(source, adapter):
    """Return whether an optional credentialed direct path is ready to execute.

    A false result never disables search-engine discovery for the source.
    """
    if adapter=='linkedin_job_library':
        return bool(os.getenv('LINKEDIN_JOB_LIBRARY_ACCESS_TOKEN','').strip() and os.getenv('LINKEDIN_JOB_LIBRARY_API_URL','').strip())
    if adapter=='glassdoor_jobs':
        enabled=os.getenv('GLASSDOOR_API_ENABLED','').strip().casefold() in {'1','true','yes','on'}
        return enabled and all(os.getenv(k,'').strip() for k in ('GLASSDOOR_PARTNER_ID','GLASSDOOR_API_KEY','GLASSDOOR_USER_IP'))
    return True


def _relative_published(text):
    raw=_text(text).casefold()
    now=timezone.now().astimezone(dt_timezone.utc)
    if raw in {'today','just now','now'}: return now.isoformat()
    if raw=='yesterday': return (now-timezone.timedelta(days=1)).isoformat()
    m=re.search(r'\b(\d{1,3})\s*(minute|min|hour|hr|day|week|month)s?\s+ago\b',raw)
    if not m: return ''
    n=int(m.group(1)); unit=m.group(2)
    if unit.startswith(('minute','min')): delta=timezone.timedelta(minutes=n)
    elif unit.startswith(('hour','hr')): delta=timezone.timedelta(hours=n)
    elif unit.startswith('day'): delta=timezone.timedelta(days=n)
    elif unit.startswith('week'): delta=timezone.timedelta(weeks=n)
    else: delta=timezone.timedelta(days=n*30)
    return (now-delta).isoformat()


def _request_json(source, adapter, url, params=None, cache_seconds=None, headers=None, timeout=20):
    ttl=int(cache_seconds or DEFAULT_CACHE_SECONDS.get(adapter,1800))
    key=_cache_key(url,params or {})
    cached=cache.get(key)
    if cached is not None:
        _network_metric(source,adapter,url,cached=True,ok=True,count=(len(cached) if isinstance(cached,list) else 0),query=(params or {}).get('q') or (params or {}).get('keyword') or '')
        return cached,''
    started=time.monotonic(); response=None
    hdr={'User-Agent':'ScoutBox/0.11.152 (+community hiring-signal discovery)','Accept':'application/json,text/plain,*/*'}
    hdr.update(headers or {})
    try:
        response=requests.get(url,params=params or {},headers=hdr,timeout=timeout)
        response.raise_for_status()
        data=response.json()
        cache.set(key,data,ttl)
        _network_metric(source,adapter,response.url,cached=False,ok=True,elapsed_ms=int((time.monotonic()-started)*1000),bytes_downloaded=len(response.content),query=(params or {}).get('q') or (params or {}).get('keyword') or '')
        return data,''
    except Exception as exc:
        _network_metric(source,adapter,(getattr(response,'url',None) or url),cached=False,ok=False,elapsed_ms=int((time.monotonic()-started)*1000),bytes_downloaded=len(getattr(response,'content',b'') or b''),error=str(exc),query=(params or {}).get('q') or (params or {}).get('keyword') or '')
        return None,str(exc)


def _request_text(source, adapter, url, params=None, cache_seconds=None, headers=None, timeout=20):
    ttl=int(cache_seconds or DEFAULT_CACHE_SECONDS.get(adapter,1800))
    key=_cache_key(url,params or {})
    cached=cache.get(key)
    if isinstance(cached,str):
        _network_metric(source,adapter,url,cached=True,ok=True,query=(params or {}).get('q') or (params or {}).get('keyword') or '')
        return cached,''
    started=time.monotonic(); response=None
    hdr={'User-Agent':'ScoutBox/0.11.152 (+community hiring-signal discovery)','Accept':'text/html,application/rss+xml,application/xml,text/plain,*/*'}
    hdr.update(headers or {})
    try:
        response=requests.get(url,params=params or {},headers=hdr,timeout=timeout)
        response.raise_for_status(); text=response.text
        cache.set(key,text,ttl)
        _network_metric(source,adapter,response.url,cached=False,ok=True,elapsed_ms=int((time.monotonic()-started)*1000),bytes_downloaded=len(response.content),query=(params or {}).get('q') or (params or {}).get('keyword') or '')
        return text,''
    except Exception as exc:
        _network_metric(source,adapter,(getattr(response,'url',None) or url),cached=False,ok=False,elapsed_ms=int((time.monotonic()-started)*1000),bytes_downloaded=len(getattr(response,'content',b'') or b''),error=str(exc),query=(params or {}).get('q') or (params or {}).get('keyword') or '')
        return '',str(exc)


def _row(source, *, title, url, snippet='', company='', remote_text='', published_at='', item_id='', adapter='', extra=None):
    clean={
        'title':_text(title)[:300], 'url':str(url or '').strip()[:2000], 'snippet':_plain(snippet,10000),
        'company':_text(company)[:220], 'remote_text':_text(remote_text)[:220], 'published_at':_iso(published_at),
        '_direct_source':True, '_direct_adapter':adapter, '_direct_item_id':str(item_id or '')[:160],
        '_acquisition_path':(
            'Community API' if adapter in {'hn_whoishiring','dev_hiring','reddit'} else
            ('RSS / feed' if adapter in {'wwr_rss','lobsters_jobs'} else
            ('Direct page' if adapter in {'indiehackers_jobs','wellfound_page'} else
            ('Credentialed job API' if adapter in {'linkedin_job_library','glassdoor_jobs'} else
            ('ATS API' if adapter in {'greenhouse','lever','ashby','smartrecruiters'} else 'Direct job API'))))
        ),
        '_publication_authoritative': bool(_iso(published_at)),
    }
    if adapter in {'hn_whoishiring','reddit','lobsters_jobs','dev_hiring','indiehackers_jobs',FORUM_DIRECT_ADAPTER}:
        clean['_community_hiring_signal']=True
        clean['_community_kind']=(
            'hacker_news_hiring' if adapter=='hn_whoishiring' else
            ('reddit_post' if adapter=='reddit' else
            ('forum_discussion' if adapter==FORUM_DIRECT_ADAPTER else 'community_hiring_post'))
        )
    if extra: clean.update(extra)
    return clean


def _remoteok(source, campaign, search_profile, limit):
    data,err=_request_json(source,'remoteok','https://remoteok.com/api',cache_seconds=1800)
    if err or not isinstance(data,list): return [],err
    rows=[]
    for item in data:
        if not isinstance(item,dict) or not item.get('position'): continue
        rows.append(_row(source,title=item.get('position'),url=item.get('url') or item.get('apply_url'),snippet=item.get('description') or item.get('tags'),company=item.get('company'),remote_text=' · '.join(x for x in [_text(item.get('location')),_text(item.get('tags'))] if x),published_at=item.get('date') or item.get('epoch'),item_id=item.get('id'),adapter='remoteok',extra={'_role_location_hint':_text(item.get('location'))[:800]}))
    return rows[:max(limit*4,60)],''


def _remotive(source, campaign, search_profile, limit):
    data,err=_request_json(source,'remotive','https://remotive.com/api/remote-jobs',cache_seconds=3600)
    if err or not isinstance(data,dict): return [],err
    rows=[]
    for item in data.get('jobs') or []:
        if not isinstance(item,dict): continue
        rows.append(_row(source,title=item.get('title'),url=item.get('url'),snippet=item.get('description'),company=item.get('company_name'),remote_text=' · '.join(x for x in [_text(item.get('candidate_required_location')),_text(item.get('job_type'))] if x),published_at=item.get('publication_date'),item_id=item.get('id'),adapter='remotive',extra={'_role_location_hint':_text(item.get('candidate_required_location'))[:800]}))
    return rows[:max(limit*4,80)],''


def _himalayas(source, campaign, search_profile, limit):
    # Rotate several compact campaign/specialty queries instead of one static role phrase.
    # The API refreshes daily, so each query is cached for a day while the run still covers
    # a wider niche surface across repeated executions.
    rows=[]; errors=[]
    for query in _direct_query_variants(campaign,search_profile,adapter='himalayas',max_queries=5):
        data,err=_request_json(source,'himalayas','https://himalayas.app/jobs/api/search',params={'q':query,'sort':'recent','page':1},cache_seconds=86400)
        if err or not isinstance(data,dict):
            if err: errors.append(f'{query}: {err}')
            continue
        batch=[]
        for item in data.get('jobs') or []:
            if not isinstance(item,dict): continue
            restrictions=[x.get('name') if isinstance(x,dict) else str(x) for x in (item.get('locationRestrictions') or [])]
            salary=''
            if item.get('minSalary') or item.get('maxSalary'):
                salary=f"{item.get('currency') or ''} {item.get('minSalary') or ''}-{item.get('maxSalary') or ''} {item.get('salaryPeriod') or ''}".strip()
            batch.append(_row(source,title=item.get('title'),url=item.get('applicationLink') or f"https://himalayas.app/jobs/{item.get('guid') or ''}",snippet=' '.join(x for x in [_plain(item.get('description')),salary] if x),company=item.get('companyName'),remote_text=('Worldwide' if not restrictions else ', '.join(restrictions)),published_at=item.get('pubDate'),item_id=item.get('guid'),adapter='himalayas',extra={'_direct_query':query,'_role_location_hint':', '.join(restrictions[:8])[:800]}))
        _merge_rows_unique(rows,batch)
        if len(rows)>=max(limit*4,60): break
    return rows[:max(limit*4,80)], '; '.join(errors[:4])


def _jobicy(source, campaign, search_profile, limit):
    params={'count':min(200,max(60,limit*4))}
    data,err=_request_json(source,'jobicy','https://jobicy.com/api/v2/remote-jobs',params=params,cache_seconds=3600)
    if err or not isinstance(data,dict): return [],err
    rows=[]
    for item in data.get('jobs') or []:
        if not isinstance(item,dict): continue
        salary=''
        if item.get('salaryMin') or item.get('salaryMax'):
            salary=f"{item.get('salaryCurrency') or ''} {item.get('salaryMin') or ''}-{item.get('salaryMax') or ''} {item.get('salaryPeriod') or ''}".strip()
        rows.append(_row(source,title=item.get('jobTitle'),url=item.get('url'),snippet=' '.join(x for x in [item.get('jobExcerpt'),item.get('jobDescription'),salary] if x),company=item.get('companyName'),remote_text=' · '.join(x for x in [_text(item.get('jobGeo')),_text(item.get('jobType'))] if x),published_at=item.get('pubDate'),item_id=item.get('id'),adapter='jobicy',extra={'_role_location_hint':_text(item.get('jobGeo'))[:800]}))
    return rows[:max(limit*4,80)],''


def _wwr(source, campaign, search_profile, limit):
    text,err=_request_text(source,'wwr_rss','https://weworkremotely.com/remote-jobs.rss',cache_seconds=3600)
    if err or not text: return [],err
    feed=feedparser.parse(text); rows=[]
    for item in feed.entries or []:
        title=_text(item.get('title'))
        company=''
        if ':' in title:
            maybe_company,maybe_role=title.split(':',1)
            if maybe_company and maybe_role:
                company=maybe_company.strip(); title=maybe_role.strip()
        rows.append(_row(source,title=title,url=item.get('link'),snippet=item.get('summary') or item.get('description'),company=company,remote_text='Remote',published_at=item.get('published'),item_id=item.get('id') or item.get('guid') or item.get('link'),adapter='wwr_rss'))
    return rows[:max(limit*4,80)],''


def _hn_comment_title(text, company=''):
    # Pull one role-shaped phrase from an employer comment.  The AI gate still decides
    # whether the comment represents a concrete current opportunity.
    clean=_plain(text,8000)
    patterns=[
        r'(?i)\b((?:principal|staff|senior|lead|junior)?\s*(?:embedded|firmware|linux|kernel|systems?|platform|devops|security|technical)?\s*(?:software\s+)?(?:engineer|developer|architect|consultant|writer|researcher|scientist|programmer)(?:\s+[A-Za-z0-9+#./-]+){0,5})\b',
    ]
    for pattern in patterns:
        m=re.search(pattern,clean)
        if m:
            title=_text(m.group(1)).strip(' ,;:-')
            if 5<=len(title)<=120: return title
    return (company+' — HN Who is Hiring').strip(' —')[:160] or 'HN Who is Hiring opportunity'


def _hn_company(text):
    plain=_plain(text,1500)
    first=plain.split('|',1)[0].strip(' -–—:')
    first=re.sub(r'(?i)^\s*(?:company|employer)\s*[:\-]\s*','',first).strip()
    if 2<=len(first)<=100 and not _ROLE_WORDS.search(first): return first
    return ''


def _hn_candidate_story_ids(source):
    """Return current/recent HN Who is Hiring story IDs, newest exact month first.

    Algolia's ``hitsPerPage`` limits only this story lookup. Once a thread is selected,
    ScoutBox enumerates its top-level comments from the HN item API rather than treating
    the first 20 Algolia story hits as job records.
    """
    ids=[]
    now=timezone.now().astimezone(dt_timezone.utc)
    month_queries=[]
    for offset in (0,-1,-2):
        year=now.year + ((now.month + offset - 1)//12)
        month=((now.month + offset - 1)%12)+1
        month_queries.append(f'Ask HN: Who is hiring? ({calendar.month_name[month]} {year})')
    for query_text in month_queries+['Ask HN: Who is hiring?']:
        found,err=_request_json(source,'hn_whoishiring','https://hn.algolia.com/api/v1/search_by_date',params={'query':query_text,'tags':'story,author_whoishiring','hitsPerPage':20},cache_seconds=1800)
        if err or not isinstance(found,dict):
            continue
        hits=found.get('hits') or []
        # Exact monthly searches should contribute their exact-title match before broad results.
        hits=sorted([h for h in hits if isinstance(h,dict)], key=lambda h: (0 if str(h.get('title') or '').casefold()==query_text.casefold() else 1, -(int(h.get('created_at_i') or 0))))
        for hit in hits:
            title=str(hit.get('title') or '')
            if 'who is hiring?' not in title.casefold():
                continue
            object_id=str(hit.get('objectID') or '').strip()
            if object_id.isdigit() and object_id not in ids:
                ids.append(object_id)
    # Recovery seeds only; dynamically discovered current threads stay ahead of them.
    for value in ('49522897','49156683','48747976'):
        if value not in ids:
            ids.append(value)
    return ids[:8]


def _hn_story_comment_rows(source, story_id, limit):
    story,story_err=_request_json(source,'hn_whoishiring',f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json',cache_seconds=1800)
    if story_err or not isinstance(story,dict):
        return [],story_err
    title=str(story.get('title') or '')
    if 'who is hiring?' not in title.casefold():
        return [],''
    kids=[int(x) for x in (story.get('kids') or []) if str(x).isdigit()]
    if not kids:
        return [],''

    def fetch_comment(cid):
        key=f'scoutbox:fresh:hn-comment:{cid}'
        cached=cache.get(key)
        if isinstance(cached,dict):
            return cached
        try:
            r=requests.get(f'https://hacker-news.firebaseio.com/v0/item/{cid}.json',headers={'User-Agent':'ScoutBox/0.11.12 (+direct HN hiring discovery)'},timeout=10)
            r.raise_for_status(); data=r.json()
            cache.set(key,data,1800)
            return data
        except Exception:
            return None

    comments=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for item in pool.map(fetch_comment,kids):
            if isinstance(item,dict) and not item.get('deleted') and not item.get('dead') and item.get('text'):
                comments.append(item)
    rows=[]
    for item in comments:
        text=_plain(item.get('text'),12000)
        company=_hn_company(text)
        comment_id=item.get('id')
        rows.append(_row(
            source,title=_hn_comment_title(text,company),url=f'https://news.ycombinator.com/item?id={comment_id}',
            snippet=text,company=company,remote_text=('Remote' if _REMOTE_HINT.search(text) else ''),
            published_at=item.get('time'),item_id=comment_id,adapter='hn_whoishiring',
            extra={'_community_thread_url':f'https://news.ycombinator.com/item?id={story_id}', '_community_thread_title':_text(story.get('title')), '_community_comment_url':f'https://news.ycombinator.com/item?id={comment_id}'}
        ))
    return rows,''


def _hn_direct_page_rows(source, campaign, search_profile, limit):
    rows=[]
    page_specs=[
        ('hn_jobs','https://news.ycombinator.com/jobs',lambda p: p.startswith('/item') or p.startswith('/jobs') or bool(p)),
        ('hnhiring','https://hnhiring.com/search',lambda p: True),
        ('hnhiring_remote','https://hnhiring.com/search?locations=remote',lambda p: True),
        ('hnhiring_heroku','https://hnhiring.herokuapp.com/search',lambda p: True),
    ]
    for adapter,url,path_hint in page_specs:
        try:
            batch,err=_direct_job_page(source,campaign,search_profile,max(10,limit//2),adapter=adapter,url=url,path_hint=path_hint)
            if batch:
                for row in batch:
                    row['adapter']='hn_whoishiring'
                    row.setdefault('extra',{})['_direct_hiring_surface']=url
                rows.extend(batch)
        except Exception:
            continue
    return rows[:max(limit*3,60)]


def _hn_whoishiring(source, campaign, search_profile, limit):
    """Scan Hacker News hiring surfaces plus monthly HN threads.

    YC startup vacancies are intentionally handled by the separate ``yc_jobs`` adapter
    so each enabled source has independent coverage and Search Activity provenance.
    """
    rows=[]; errors=[]; seen=set()
    story_ids=_hn_candidate_story_ids(source)
    if not story_ids:
        errors.append('No current Hacker News Who is Hiring thread found.')
    # Fully enumerate the newest available monthly thread. Previous releases repeatedly
    # truncated the comment list before relevance scoring, starving later HN comments.
    # Stop after the first live monthly thread so full coverage does not multiply request
    # volume across several historical months on every run.
    for story_id in story_ids:
        batch,err=_hn_story_comment_rows(source,story_id,limit)
        if err:
            errors.append(str(err)); continue
        if not batch:
            continue
        for row in batch:
            key=str(row.get('item_id') or row.get('url') or '')
            if key and key in seen: continue
            if key: seen.add(key)
            rows.append(row)
        break
    for row in _hn_direct_page_rows(source,campaign,search_profile,limit):
        row['_community_hiring_signal']=True
        row['_community_kind']='hacker_news_hiring'
        key=str(row.get('url') or row.get('item_id') or '')
        if key and key in seen: continue
        if key: seen.add(key)
        rows.append(row)
    if not rows and errors:
        return [],errors[0]
    return rows,''


def _lobsters_jobs(source, campaign, search_profile, limit):
    text,err=_request_text(source,'lobsters_jobs','https://lobste.rs/t/job.rss',cache_seconds=1800)
    if err or not text: return [],err
    feed=feedparser.parse(text); rows=[]
    for item in feed.entries or []:
        title=_text(item.get('title'))
        snippet=item.get('summary') or item.get('description') or ''
        rows.append(_row(source,title=title,url=item.get('link'),snippet=snippet,company='',remote_text=('Remote' if _REMOTE_HINT.search(_plain(snippet,4000)+' '+title) else ''),published_at=item.get('published') or item.get('updated'),item_id=item.get('id') or item.get('guid') or item.get('link'),adapter='lobsters_jobs'))
    return rows[:max(limit*4,80)],''


def _dev_hiring(source, campaign, search_profile, limit):
    # DEV/Forem exposes recently published articles publicly; the hiring tag provides a
    # narrow first-party community surface and the local prefilter rejects generic advice.
    data,err=_request_json(source,'dev_hiring','https://dev.to/api/articles',params={'tag':'hiring','per_page':min(100,max(30,limit*4)),'page':1},cache_seconds=1800)
    if err or not isinstance(data,list): return [],err
    rows=[]
    for item in data:
        if not isinstance(item,dict): continue
        user=item.get('user') if isinstance(item.get('user'),dict) else {}
        org=item.get('organization') if isinstance(item.get('organization'),dict) else {}
        snippet=' '.join(x for x in [_text(item.get('description')),_text(item.get('tag_list'))] if x)
        rows.append(_row(source,title=item.get('title'),url=item.get('canonical_url') or item.get('url'),snippet=snippet,company=org.get('name') or user.get('name'),remote_text=('Remote' if _REMOTE_HINT.search(snippet+' '+_text(item.get('title'))) else ''),published_at=item.get('published_at') or item.get('published_timestamp'),item_id=item.get('id'),adapter='dev_hiring'))
    return rows[:max(limit*4,80)],''


def _jsonld_job_rows(source, adapter, html_text, base_url):
    soup=BeautifulSoup(html_text or '','html.parser'); rows=[]
    def walk(value):
        if isinstance(value,list):
            for x in value: yield from walk(x)
        elif isinstance(value,dict):
            if str(value.get('@type') or '').casefold()=='jobposting': yield value
            graph=value.get('@graph')
            if graph is not None: yield from walk(graph)
    for tag in soup.find_all('script',attrs={'type':'application/ld+json'}):
        try: data=json.loads(tag.string or tag.get_text() or '')
        except Exception: continue
        for item in walk(data):
            org=item.get('hiringOrganization') if isinstance(item.get('hiringOrganization'),dict) else {}
            loc=item.get('jobLocation') or item.get('applicantLocationRequirements') or ''
            url=item.get('url') or item.get('sameAs') or ''
            if url: url=urllib.parse.urljoin(base_url,str(url))
            rows.append(_row(source,title=item.get('title'),url=url,snippet=item.get('description'),company=org.get('name'),remote_text=_text(loc),published_at=item.get('datePosted') or item.get('validThrough'),item_id=item.get('identifier') or url,adapter=adapter))
    return rows,soup


def _direct_job_page(source, campaign, search_profile, limit, *, adapter, url, path_hint):
    text,err=_request_text(source,adapter,url,cache_seconds=1800)
    if err or not text: return [],err
    rows,soup=_jsonld_job_rows(source,adapter,text,url)
    seen={str(r.get('url') or '') for r in rows if r.get('url')}
    for a in soup.find_all('a',href=True):
        href=str(a.get('href') or '')
        absolute=urllib.parse.urljoin(url,href)
        path=urllib.parse.urlsplit(absolute).path.casefold()
        if not path_hint(path): continue
        if absolute in seen: continue
        title=_text(a.get_text(' ',strip=True))
        if len(title)<4 or len(title)>220: continue
        card=a.find_parent(['article','li','section','div'])
        card_text=_plain(card.get_text(' ',strip=True) if card else title,6000)
        if len(card_text)<len(title)+10: continue
        published=''
        time_tag=card.find('time') if card else None
        if time_tag:
            published=_iso(time_tag.get('datetime') or time_tag.get_text(' ',strip=True))
        if not published: published=_relative_published(card_text)
        rows.append(_row(source,title=title,url=absolute,snippet=card_text,company='',remote_text=('Remote' if _REMOTE_HINT.search(card_text) else ''),published_at=published,item_id=absolute,adapter=adapter))
        seen.add(absolute)
        if len(rows)>=max(limit*5,100): break
    return rows[:max(limit*5,100)],''


def _yc_jobs(source, campaign, search_profile, limit):
    """Acquire YC startup vacancies directly from YC-owned hiring surfaces.

    YC used to be scanned as a side effect of the Hacker News Who is Hiring adapter.
    Keeping it as its own adapter gives the configured ``YC Work at a Startup`` source
    an independent attempt/result history and prevents HN scheduler starvation from
    silently removing YC coverage.
    """
    rows=[]; errors=[]
    surfaces=[
        ('https://www.ycombinator.com/jobs', lambda p: '/companies/' in p and '/jobs/' in p),
        ('https://www.ycombinator.com/jobs/role/all', lambda p: '/companies/' in p and '/jobs/' in p),
        ('https://www.workatastartup.com/jobs', lambda p: '/companies/' in p and '/jobs/' in p),
    ]
    for url,path_hint in surfaces:
        try:
            batch,err=_direct_job_page(source,campaign,search_profile,max(10,limit),adapter='yc_jobs',url=url,path_hint=path_hint)
        except Exception as exc:
            batch=[]; err=str(exc)
        if err:
            errors.append(f'{url}: {err}')
        for row in batch or []:
            row['_direct_hiring_surface']=url
        _merge_rows_unique(rows,batch or [])
    return rows[:max(limit*5,100)], '; '.join(errors[:4])


def _indiehackers_jobs(source, campaign, search_profile, limit):
    return _direct_job_page(source,campaign,search_profile,limit,adapter='indiehackers_jobs',url='https://www.indiehackers.com/jobs',path_hint=lambda p: p.startswith('/job/') or (p.startswith('/jobs/') and p!='/jobs/'))


def _wellfound_page(source, campaign, search_profile, limit):
    return _direct_job_page(source,campaign,search_profile,limit,adapter='wellfound_page',url='https://wellfound.com/jobs',path_hint=lambda p: '/jobs/' in p and p.rstrip('/')!='/jobs')


def _linkedin_job_library(source, campaign, search_profile, limit):
    token=os.getenv('LINKEDIN_JOB_LIBRARY_ACCESS_TOKEN','').strip()
    api_url=os.getenv('LINKEDIN_JOB_LIBRARY_API_URL','').strip()
    if not token or not api_url: return [],''
    version=os.getenv('LINKEDIN_JOB_LIBRARY_VERSION','202606').strip() or '202606'
    headers={'Authorization':'Bearer '+token,'X-RestLi-Protocol-Version':'2.0.0','LinkedIn-Version':version}
    rows=[]; errors=[]
    for q in _direct_query_variants(campaign,search_profile,adapter='linkedin_job_library',max_queries=4):
        data,err=_request_json(source,'linkedin_job_library',api_url,params={'q':'criteria','keyword':q,'start':0,'count':min(24,max(10,limit*2))},cache_seconds=900,headers=headers)
        if err or not isinstance(data,dict):
            if err: errors.append(f'{q}: {err}')
            continue
        items=data.get('elements') or data.get('jobs') or data.get('results') or []
        batch=[]
        for item in items if isinstance(items,list) else []:
            if not isinstance(item,dict): continue
            details=item.get('jobDetails') if isinstance(item.get('jobDetails'),dict) else item
            status=_text(details.get('status') or item.get('status')).casefold()
            if details.get('isClosed') is True or status in {'closed','expired','inactive'}: continue
            target=details.get('jobPostingUrl') or details.get('jobUrl') or details.get('url') or item.get('jobPostingUrl') or item.get('url')
            title=details.get('jobTitle') or details.get('title') or item.get('jobTitle') or item.get('title')
            company=details.get('companyName') or item.get('companyName') or _text(details.get('company'))
            snippet=details.get('description') or details.get('jobDescription') or item.get('description') or ''
            published=details.get('openDate') or details.get('servedAt') or details.get('listedAt') or item.get('openDate') or item.get('servedAt')
            batch.append(_row(source,title=title,url=target,snippet=snippet,company=company,remote_text=_text(details.get('location') or item.get('location')),published_at=published,item_id=details.get('jobPostingId') or item.get('id') or target,adapter='linkedin_job_library',extra={'_linkedin_paid_job_library':True,'_direct_query':q}))
        _merge_rows_unique(rows,batch)
        if len(rows)>=max(limit*4,80): break
    return rows[:max(limit*4,80)], '; '.join(errors[:4])


def _glassdoor_jobs(source, campaign, search_profile, limit):
    if not _adapter_configured(source,'glassdoor_jobs'): return [],''
    rows=[]; errors=[]
    location=_text(getattr(campaign,'location',''))
    for q in _direct_query_variants(campaign,search_profile,adapter='glassdoor_jobs',max_queries=4):
        params={
            'v':'1.1','format':'json','t.p':os.getenv('GLASSDOOR_PARTNER_ID','').strip(),
            't.k':os.getenv('GLASSDOOR_API_KEY','').strip(),'userip':os.getenv('GLASSDOOR_USER_IP','').strip(),
            'useragent':os.getenv('GLASSDOOR_USER_AGENT','ScoutBox/0.10.35').strip(),
            'action':'jobs','q':q,'ps':min(100,max(20,limit*3)),'pn':1,
        }
        if location: params['l']=location
        data,err=_request_json(source,'glassdoor_jobs','https://api.glassdoor.com/api/api.htm',params=params,cache_seconds=1800)
        if err or not isinstance(data,dict):
            if err: errors.append(f'{q}: {err}')
            continue
        response=data.get('response') if isinstance(data.get('response'),dict) else {}
        items=response.get('jobListings') or response.get('jobs') or []
        batch=[]
        for item in items if isinstance(items,list) else []:
            if not isinstance(item,dict): continue
            employer=item.get('employer') if isinstance(item.get('employer'),dict) else {}
            item_location=item.get('location') if isinstance(item.get('location'),dict) else item.get('location')
            batch.append(_row(source,title=item.get('jobTitle') or item.get('title'),url=item.get('jobViewUrl') or item.get('url'),snippet=item.get('jobDescription') or item.get('description'),company=employer.get('name') or item.get('employerName'),remote_text=_text(item_location),published_at=item.get('datePosted'),item_id=item.get('jobListingId') or item.get('id'),adapter='glassdoor_jobs',extra={'_glassdoor_attribution_required':True,'_direct_query':q}))
        _merge_rows_unique(rows,batch)
        if len(rows)>=max(limit*4,80): break
    return rows[:max(limit*4,80)], '; '.join(errors[:4])


def _reddit_token():
    client=os.getenv('REDDIT_CLIENT_ID','').strip(); secret=os.getenv('REDDIT_CLIENT_SECRET','').strip()
    if not client or not secret: return ''
    key='scoutbox:reddit:oauth-token'; failure_key='scoutbox:reddit:oauth-token-failed'; cached=cache.get(key)
    if cached: return str(cached)
    if cache.get(failure_key): return ''
    try:
        r=requests.post('https://www.reddit.com/api/v1/access_token',auth=(client,secret),data={'grant_type':'client_credentials'},headers={'User-Agent':os.getenv('REDDIT_USER_AGENT','ScoutBox/0.11.152 community hiring-signal discovery')},timeout=max(4,min(15,int(os.getenv('SCOUTBOX_REDDIT_REQUEST_TIMEOUT_SECONDS','10') or 10))))
        r.raise_for_status(); data=r.json(); token=str(data.get('access_token') or '')
        if token:
            cache.set(key,token,max(60,int(data.get('expires_in') or 3600)-120))
            cache.delete(failure_key)
        return token
    except Exception:
        # Avoid paying the same OAuth timeout once per campaign when credentials or the
        # auth endpoint are temporarily unhealthy; public Reddit JSON remains available.
        cache.set(failure_key,True,300)
        return ''


def _reddit(source, campaign, search_profile, limit):
    token=_reddit_token(); headers={'User-Agent':os.getenv('REDDIT_USER_AGENT','ScoutBox/0.11.152 community hiring-signal discovery')}
    if token:
        headers['Authorization']='bearer '+token
        url='https://oauth.reddit.com/search'
    else:
        # This is still Reddit's own JSON listing endpoint, never a search-engine cache.
        url='https://www.reddit.com/search.json'

    # Reddit occasionally accepts the connection but responds slowly enough that a full
    # ten-query pass appears frozen. Bound both the number of queries and wall-clock time,
    # and stop early after repeated request failures. A later campaign rotation can try the
    # remaining variants without one unhealthy source monopolising the worker.
    try:
        max_queries=max(2,min(10,int(os.getenv('SCOUTBOX_REDDIT_MAX_QUERIES_PER_PASS','6') or 6)))
    except Exception:
        max_queries=6
    try:
        pass_budget=max(20,min(240,int(os.getenv('SCOUTBOX_REDDIT_PASS_MAX_SECONDS','75') or 75)))
    except Exception:
        pass_budget=75
    try:
        request_timeout=max(4,min(20,int(os.getenv('SCOUTBOX_REDDIT_REQUEST_TIMEOUT_SECONDS','10') or 10)))
    except Exception:
        request_timeout=10
    try:
        max_consecutive_errors=max(1,min(5,int(os.getenv('SCOUTBOX_REDDIT_MAX_CONSECUTIVE_ERRORS','2') or 2)))
    except Exception:
        max_consecutive_errors=2

    rows=[]; errors=[]; started=time.monotonic(); consecutive_errors=0
    # Use several rotated, compact queries. Keep hiring intent but vary specialty terms.
    for query in _direct_query_variants(campaign,search_profile,adapter='reddit',max_queries=max_queries,include_intent=True):
        if time.monotonic()-started >= pass_budget:
            errors.append('Reddit pass time budget reached; remaining queries will rotate into later runs.')
            break
        q=' '.join(re.sub(r'\b[oO][rR]\b',' ',str(query or '')).replace('(', ' ').replace(')', ' ').split())[:180]
        if not q:
            continue
        data,err=_request_json(source,'reddit',url,params={'q':q,'sort':'new','t':'month','limit':min(100,max(25,limit*3)),'raw_json':1},cache_seconds=1800,headers=headers,timeout=request_timeout)
        if err or not isinstance(data,dict):
            consecutive_errors+=1
            if err: errors.append(f'{query}: {err}')
            if consecutive_errors>=max_consecutive_errors:
                errors.append(f'Reddit request error limit reached after {consecutive_errors} consecutive errors; remaining queries will rotate into later runs.')
                break
            continue
        consecutive_errors=0
        batch=[]
        for child in ((data.get('data') or {}).get('children') or []):
            item=(child or {}).get('data') if isinstance(child,dict) else None
            if not isinstance(item,dict): continue
            permalink=item.get('permalink') or ''
            item_url='https://www.reddit.com'+permalink if permalink.startswith('/') else (item.get('url') or '')
            subreddit=_text(item.get('subreddit_name_prefixed') or item.get('subreddit'))
            batch.append(_row(source,title=item.get('title'),url=item_url,snippet=' '.join(x for x in [item.get('selftext'),subreddit] if x),company='',remote_text=('Remote' if _REMOTE_HINT.search(_text(item.get('title'))+' '+_text(item.get('selftext'))) else ''),published_at=item.get('created_utc'),item_id=item.get('id'),adapter='reddit',extra={'_reddit_subreddit':subreddit,'_reddit_author':_text(item.get('author'))[:100],'_direct_query':query}))
        _merge_rows_unique(rows,batch)
        if len(rows)>=max(limit*5,120): break
    return rows[:max(limit*5,120)], '; '.join(errors[:6])


def _known_ats_targets(adapter, max_targets=40):
    """Learn employer ATS boards from URLs ScoutBox has already encountered.

    A direct ATS URL is a high-confidence board identifier.  Preserve the employer name
    from the record that taught ScoutBox the board so API results are not labelled with
    a prettified slug when a trustworthy company name is already known.
    """
    rows=[]
    for model in (Opportunity,CompanyLead):
        try:
            for a,b,c,company in model.objects.filter(user_deleted=False).values_list('target_url','url','search_url','company').order_by('-updated_at')[:2500]:
                rows.append((a,b,c,_text(company)))
        except Exception:
            continue
    found={}
    for a,b,c,company in rows:
        for raw in (a,b,c):
            if not raw: continue
            try:
                p=urllib.parse.urlsplit(raw); host=(p.hostname or '').lower(); seg=[urllib.parse.unquote(x) for x in p.path.split('/') if x]
            except Exception: continue
            key=''; base=''
            if adapter=='greenhouse' and 'greenhouse.io' in host:
                if seg: key=seg[0]
            elif adapter=='lever' and (host in {'jobs.lever.co','jobs.eu.lever.co'} or host.endswith('.jobs.lever.co')):
                if seg: key=seg[0]; base='https://api.eu.lever.co/v0/postings' if host.endswith('.eu.lever.co') else 'https://api.lever.co/v0/postings'
            elif adapter=='ashby' and (host=='jobs.ashbyhq.com' or host.endswith('.jobs.ashbyhq.com')):
                if seg: key=seg[0]
            elif adapter=='smartrecruiters' and 'smartrecruiters.com' in host:
                if seg: key=seg[0]
            if key and re.fullmatch(r'[A-Za-z0-9._-]{2,120}',key):
                prior=found.get(key)
                learned_company=company_from_ats_url(raw) or (company if is_plausible_company_name(company) else '')
                found[key]=(base or (prior[0] if prior else ''), learned_company or (prior[1] if prior else ''))
            if len(found)>=max_targets: break
        if len(found)>=max_targets: break
    return [(key,base,company) for key,(base,company) in found.items()]

def _greenhouse(source, campaign, search_profile, limit):
    rows=[]; errors=[]
    for token,_,known_company in _known_ats_targets('greenhouse',max_targets=10):
        data,err=_request_json(source,'greenhouse',f'https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(token)}/jobs',params={'content':'true'},cache_seconds=1800)
        if err: errors.append(f'{token}: {err}'); continue
        for item in (data or {}).get('jobs',[]) if isinstance(data,dict) else []:
            if not isinstance(item,dict): continue
            location=_text((item.get('location') or {}).get('name') if isinstance(item.get('location'),dict) else item.get('location'))
            rows.append(_row(source,title=item.get('title'),url=item.get('absolute_url'),snippet=item.get('content'),company=known_company or token.replace('-',' ').replace('_',' ').title(),remote_text=location,published_at='',item_id=item.get('id'),adapter='greenhouse',extra={'_ats_board':token,'_source_updated_at':_iso(item.get('updated_at'))}))
    return rows, '; '.join(errors[:4])


def _lever(source, campaign, search_profile, limit):
    rows=[]; errors=[]
    for site,base,known_company in _known_ats_targets('lever',max_targets=10):
        site_rows=[]
        # Lever is one of the direct ATS families with provider-supported worldwide
        # endpoint variants.  Query at most two endpoints per learned board, keep the
        # learned/default endpoint first, and deduplicate postings across variants.
        endpoints=direct_endpoint_variants(
            'lever', base or 'https://api.lever.co/v0/postings', limit=2
        )
        for endpoint in endpoints:
            data,err=_request_json(source,'lever',f'{endpoint}/{urllib.parse.quote(site)}',params={'mode':'json'},cache_seconds=1800)
            if err:
                try:
                    endpoint_name=urllib.parse.urlsplit(endpoint).hostname or endpoint
                except Exception:
                    endpoint_name=endpoint
                errors.append(f'{site} {endpoint_name}: {err}')
                continue
            batch=[]
            for item in data if isinstance(data,list) else []:
                cats=item.get('categories') if isinstance(item.get('categories'),dict) else {}
                batch.append(_row(source,title=item.get('text'),url=item.get('hostedUrl') or item.get('applyUrl'),snippet=' '.join(x for x in [item.get('descriptionPlain'),item.get('additionalPlain'),_text(item.get('lists'))] if x),company=known_company or site.replace('-',' ').title(),remote_text=' · '.join(x for x in [_text(cats.get('location')),_text(cats.get('commitment'))] if x),published_at=item.get('createdAt'),item_id=item.get('id'),adapter='lever',extra={'_ats_board':site,'_direct_endpoint':endpoint}))
            _merge_rows_unique(site_rows,batch)
        _merge_rows_unique(rows,site_rows)
        if len(rows)>=max(limit*4,80):
            break
    return rows, '; '.join(errors[:4])


def _ashby(source, campaign, search_profile, limit):
    rows=[]; errors=[]
    for board,_,known_company in _known_ats_targets('ashby',max_targets=10):
        data,err=_request_json(source,'ashby',f'https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(board)}',params={'includeCompensation':'true'},cache_seconds=1800)
        if err: errors.append(f'{board}: {err}'); continue
        for item in (data or {}).get('jobs',[]) if isinstance(data,dict) else []:
            rows.append(_row(source,title=item.get('title'),url=item.get('jobUrl') or item.get('applyUrl'),snippet=' '.join(x for x in [item.get('descriptionPlain'),item.get('descriptionHtml'),_text(item.get('compensation'))] if x),company=known_company or board.replace('-',' ').title(),remote_text=' · '.join(x for x in [_text(item.get('location')),_text(item.get('workplaceType'))] if x),published_at=item.get('publishedAt') or item.get('createdAt'),item_id=item.get('id') or item.get('jobUrl'),adapter='ashby',extra={'_ats_board':board}))
    return rows, '; '.join(errors[:4])


def _smartrecruiters(source, campaign, search_profile, limit):
    rows=[]; errors=[]
    # SmartRecruiters company boards can be browsed broadly.  Fetch the open board first
    # and let ScoutBox prefilter locally; only fall back to rotated keywords if the public
    # board endpoint returns no rows for that employer.
    for company,_,known_company in _known_ats_targets('smartrecruiters',max_targets=10):
        company_rows=[]
        data,err=_request_json(source,'smartrecruiters',f'https://api.smartrecruiters.com/v1/companies/{urllib.parse.quote(company)}/postings',params={'limit':100,'offset':0},cache_seconds=1800)
        if err:
            errors.append(f'{company}: {err}')
        for item in (data or {}).get('content',[]) if isinstance(data,dict) else []:
            if not isinstance(item,dict): continue
            location=item.get('location') if isinstance(item.get('location'),dict) else {}
            ident=item.get('id') or item.get('uuid')
            target=item.get('ref') or (f'https://jobs.smartrecruiters.com/{company}/{ident}' if ident else '')
            company_rows.append(_row(source,title=item.get('name'),url=target,snippet=' '.join(x for x in [_text(item.get('department')),_text(item.get('function')),_text(item.get('typeOfEmployment'))] if x),company=known_company or company.replace('-',' ').title(),remote_text=' · '.join(x for x in [_text(location),('Remote' if location.get('remote') else '')] if x),published_at=item.get('releasedDate') or item.get('createdOn'),item_id=ident,adapter='smartrecruiters',extra={'_ats_board':company,'_direct_query':'board browse'}))
        if not company_rows:
            for q in _direct_query_variants(campaign,search_profile,adapter='smartrecruiters',max_queries=3):
                data,err=_request_json(source,'smartrecruiters',f'https://api.smartrecruiters.com/v1/companies/{urllib.parse.quote(company)}/postings',params={'q':q,'limit':100,'offset':0},cache_seconds=1800)
                if err:
                    errors.append(f'{company} {q}: {err}'); continue
                batch=[]
                for item in (data or {}).get('content',[]) if isinstance(data,dict) else []:
                    if not isinstance(item,dict): continue
                    location=item.get('location') if isinstance(item.get('location'),dict) else {}
                    ident=item.get('id') or item.get('uuid')
                    target=item.get('ref') or (f'https://jobs.smartrecruiters.com/{company}/{ident}' if ident else '')
                    batch.append(_row(source,title=item.get('name'),url=target,snippet=' '.join(x for x in [_text(item.get('department')),_text(item.get('function')),_text(item.get('typeOfEmployment'))] if x),company=known_company or company.replace('-',' ').title(),remote_text=' · '.join(x for x in [_text(location),('Remote' if location.get('remote') else '')] if x),published_at=item.get('releasedDate') or item.get('createdOn'),item_id=ident,adapter='smartrecruiters',extra={'_ats_board':company,'_direct_query':q}))
                _merge_rows_unique(company_rows,batch)
                if company_rows: break
        _merge_rows_unique(rows,company_rows)
        if len(rows)>=max(limit*4,80): break
    return rows, '; '.join(errors[:4])


def _forum_generic(source, campaign, search_profile, limit, *, should_stop=None):
    """Native-first forum acquisition with browse-before-search semantics.

    Forum sources are user-facing Source=Forum.  ScoutBox first browses known
    marketplace/jobs/recent listing pages for the forum as a whole, then falls back to
    broad native forum searches.  It avoids overly specific native searches such as
    "looking for contractor qemu" that usually return zero results on forum software.
    """
    cfg=source.config_json if isinstance(source.config_json,dict) else {}
    base=str(cfg.get('forum_base_url') or source.base_url or '').strip().rstrip('/')
    software=str(cfg.get('forum_software') or '').strip().lower()
    path=str(cfg.get('forum_search_path') or '').strip()
    if not base:
        return [], 'Forum base URL is not configured.'
    rows=[]; errors=[]; seen=set()
    per_target=max(8,min(24,int(limit or 12)))
    try:
        forum_timeout=max(3,min(5,int(os.environ.get('SCOUTBOX_FORUM_FETCH_TIMEOUT_SECONDS','5') or 5)))
    except Exception:
        forum_timeout=5
    try:
        listing_url_cap=max(1,min(1,int(os.environ.get('SCOUTBOX_FORUM_LISTING_URLS_PER_SOURCE','1') or 1)))
    except Exception:
        listing_url_cap=1
    try:
        native_query_cap=max(0,min(1,int(os.environ.get('SCOUTBOX_FORUM_NATIVE_SEARCHES_PER_SOURCE','1') or 1)))
    except Exception:
        native_query_cap=1

    def stop_requested():
        try:
            return bool(should_stop and should_stop())
        except Exception:
            return False

    def add_items(parsed, *, acquisition_path, query='', listing_label=''):
        for item in parsed or []:
            if not isinstance(item,dict):
                continue
            item_url=str(item.get('url') or '').strip()
            key=item_url or str(item.get('item_id') or '')
            if not key or key in seen:
                continue
            seen.add(key)
            item['_forum_source']=True
            if listing_label:
                item['_forum_browse_area']=True
            if not forum_result_looks_promising(item,campaign,search_profile):
                continue
            post_date=_iso(item.get('published_at'))
            snippet=item.get('snippet') or ''
            if listing_label:
                snippet=('Forum listing '+listing_label+': '+snippet).strip()[:4000]
            rows.append(_row(
                source,
                title=item.get('title') or f'{source.name} forum opportunity',
                url=item_url,
                snippet=snippet,
                company='',
                remote_text='Forum',
                published_at=post_date,
                item_id=item.get('item_id') or item_url,
                adapter=FORUM_DIRECT_ADAPTER,
                extra={
                    '_forum_source': True,
                    '_forum_name': source.name,
                    '_forum_base_url': base,
                    '_forum_software': software,
                    '_forum_search_path': path,
                    '_forum_post_date': post_date,
                    '_forum_post_id': str(item.get('item_id') or '')[:160],
                    '_forum_query': query,
                    '_forum_browse_listing': bool(listing_label),
                    '_forum_listing_path': str(listing_label or '')[:240],
                    '_source_category_override': 'forum',
                    '_apply_via': 'forum',
                    '_acquisition_path': acquisition_path,
                    '_publication_authoritative': bool(post_date),
                },
            ))

    # 1) Browse forum marketplace/jobs/recent listings first, without exact campaign terms.
    # Keep each forum bounded. Browse the strongest marketplace/recent listing targets
    # first; do not spend seven slow HTTP attempts on every source before moving on.
    for url,params,label in forum_listing_urls(base,software,cfg,source.name)[:listing_url_cap]:
        if stop_requested():
            errors.append('Forum browse yielded to primary discovery.')
            break
        data=None; text=''; err=''
        if url.endswith('.json') or '/api/' in url:
            data,err=_request_json(source,FORUM_DIRECT_ADAPTER,url,params=params,cache_seconds=DEFAULT_CACHE_SECONDS.get(FORUM_DIRECT_ADAPTER,7200),timeout=forum_timeout,headers={'Accept':'application/json, text/plain, */*'})
            if err and not stop_requested():
                # Do not immediately repeat a timed-out/blocked JSON request as text.
                # The text fallback is only useful for a reachable endpoint that returned
                # non-JSON content; connection/HTTP failures should yield immediately.
                low_err=str(err).casefold()
                if 'json' in low_err or 'decode' in low_err or 'expecting value' in low_err:
                    text,err2=_request_text(source,FORUM_DIRECT_ADAPTER,url,params=params,cache_seconds=DEFAULT_CACHE_SECONDS.get(FORUM_DIRECT_ADAPTER,7200),timeout=forum_timeout)
                    err=err2 or err
        else:
            text,err=_request_text(source,FORUM_DIRECT_ADAPTER,url,params=params,cache_seconds=DEFAULT_CACHE_SECONDS.get(FORUM_DIRECT_ADAPTER,7200),timeout=forum_timeout)
        if stop_requested():
            errors.append('Forum browse yielded to primary discovery.')
            break
        if err:
            errors.append(f'{source.name} [listing {label}]: {err}')
            continue
        parsed=parse_forum_search_results(data,text,base_url=base,software=software,limit=per_target)
        add_items(parsed,acquisition_path='Forum listing browse',query='',listing_label=label)
        if len(rows)>=max(limit*2,per_target):
            break

    # 2) Fallback to broad native search only when listing browse did not produce enough.
    # These queries are intentionally source-wide/opportunity-wide, not exact campaign terms.
    if len(rows)<max(3,min(per_target,int(limit or 12))):
        # Fallback is deliberately tiny and broad. Exact role/technology Boolean searches
        # belong in separate search-engine discovery, not in forum-native search URLs.
        queries=build_forum_queries(campaign,search_profile,cfg,max_queries=max(1,min(2,int(limit or 12))))[:native_query_cap]
        for q in queries:
            if stop_requested():
                errors.append('Forum browse yielded to primary discovery.')
                break
            url,params=forum_search_url(base,software,path,q)
            data=None; text=''; err=''
            if software in {'discourse','nodebb'} or url.endswith('.json') or '/api/' in url:
                data,err=_request_json(source,FORUM_DIRECT_ADAPTER,url,params=params,cache_seconds=DEFAULT_CACHE_SECONDS.get(FORUM_DIRECT_ADAPTER,7200),timeout=forum_timeout,headers={'Accept':'application/json, text/plain, */*'})
                if err and not stop_requested():
                    low_err=str(err).casefold()
                    if 'json' in low_err or 'decode' in low_err or 'expecting value' in low_err:
                        text,err2=_request_text(source,FORUM_DIRECT_ADAPTER,url,params=params,cache_seconds=DEFAULT_CACHE_SECONDS.get(FORUM_DIRECT_ADAPTER,7200),timeout=forum_timeout)
                        err=err2 or err
            else:
                text,err=_request_text(source,FORUM_DIRECT_ADAPTER,url,params=params,cache_seconds=DEFAULT_CACHE_SECONDS.get(FORUM_DIRECT_ADAPTER,7200),timeout=forum_timeout)
            if stop_requested():
                errors.append('Forum browse yielded to primary discovery.')
                break
            if err:
                errors.append(f'{source.name} [{q}]: {err}')
                continue
            parsed=parse_forum_search_results(data,text,base_url=base,software=software,limit=per_target)
            add_items(parsed,acquisition_path='Forum broad native search',query=q,listing_label='')
            if len(rows)>=max(limit*3,per_target):
                break
    return rows[:max(limit*3,per_target)], '; '.join(errors[:4])

ADAPTER_FUNCTIONS = {
    'remoteok':_remoteok, 'remotive':_remotive, 'himalayas':_himalayas, 'jobicy':_jobicy,
    'wwr_rss':_wwr, 'hn_whoishiring':_hn_whoishiring, 'yc_jobs':_yc_jobs, 'lobsters_jobs':_lobsters_jobs,
    'dev_hiring':_dev_hiring, 'indiehackers_jobs':_indiehackers_jobs, 'reddit':_reddit,
    'linkedin_job_library':_linkedin_job_library, 'glassdoor_jobs':_glassdoor_jobs, 'wellfound_page':_wellfound_page,
    'greenhouse':_greenhouse, 'lever':_lever, 'ashby':_ashby, 'smartrecruiters':_smartrecruiters,
    FORUM_DIRECT_ADAPTER:_forum_generic,
}


def _safe_progress(callback, value, message):
    if not callback:
        return
    try:
        callback(int(value), str(message or ''))
    except Exception:
        pass


def _run_adapter_with_liveness(source, adapter, func, campaign, search_profile, per_source, *, progress_callback=None, should_stop=None, progress_value=None, progress_message=None):
    """Run a direct/forum adapter while keeping CampaignRun heartbeat fresh.

    Forum browsing can touch many small sites and some requests time out.  Without
    heartbeat updates during the adapter call the UI labels a healthy-but-slow run as
    stalled, and the scheduler may block the next pass behind a stale running row.
    """
    if should_stop and should_stop():
        return [], 'Stopped'
    source_name=getattr(source,'name','source')
    value=int(progress_value) if progress_value is not None else (11 if adapter==FORUM_DIRECT_ADAPTER else 13)
    verb='Browsing forum sources' if adapter==FORUM_DIRECT_ADAPTER else 'Checking direct source'
    message=str(progress_message or f'{verb}: {source_name}')[:500]
    _safe_progress(progress_callback,value,message)
    stop_event=threading.Event()
    heartbeat_thread=None
    if progress_callback:
        def heartbeat():
            close_old_connections()
            try:
                while not stop_event.wait(8):
                    close_old_connections()
                    _safe_progress(progress_callback,value,message)
            finally:
                close_old_connections()
        heartbeat_thread=threading.Thread(target=heartbeat,daemon=True)
        heartbeat_thread.start()
    try:
        if adapter==FORUM_DIRECT_ADAPTER:
            return func(source,campaign,search_profile,per_source,should_stop=should_stop)
        return func(source,campaign,search_profile,per_source)
    finally:
        stop_event.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=1)
        close_old_connections()
        _safe_progress(progress_callback,value,message)


def _source_efficiency_map(sources, days=7):
    """Return recent yield, retention and error telemetry for source ordering.

    Raw feed volume is not success. Newly created records are combined with current
    Opportunity/Hidden Lead retention so repeatedly recycled sources lose priority while
    sparse/new sources remain eligible through the rotating exploration slot.
    """
    source_ids=[getattr(source,'pk',None) for source,_adapter in sources if getattr(source,'pk',None)]
    if not source_ids:
        return {}
    window_days=max(1,int(days or 7))
    cutoff=timezone.localdate()-timedelta(days=window_days-1)
    cutoff_dt=timezone.now()-timedelta(days=window_days)
    totals={}
    def bucket_for(source_id):
        return totals.setdefault(source_id,{
            'requests':0,'results':0,'unique_results':0,'errors':0,'duplicates':0,
            'active_opportunities':0,'discarded_opportunities':0,'active_leads':0,'discarded_leads':0,
        })
    for row in SearchProviderStat.objects.filter(source_id__in=source_ids,day__gte=cutoff).values(
        'source_id','requests','results','unique_results','errors','duplicates'
    ):
        bucket=bucket_for(row['source_id'])
        for key in ('requests','results','unique_results','errors','duplicates'):
            bucket[key]+=int(row.get(key) or 0)
    for row in Opportunity.objects.filter(source_id__in=source_ids,first_seen_by_portal__gte=cutoff_dt).values(
        'source_id','user_deleted','suppressed'
    ).annotate(total=Count('id')):
        bucket=bucket_for(row['source_id'])
        key='discarded_opportunities' if bool(row.get('user_deleted') or row.get('suppressed')) else 'active_opportunities'
        bucket[key]+=int(row.get('total') or 0)
    for row in CompanyLead.objects.filter(source_id__in=source_ids,created_at__gte=cutoff_dt).values(
        'source_id','user_deleted'
    ).annotate(total=Count('id')):
        bucket=bucket_for(row['source_id'])
        key='discarded_leads' if bool(row.get('user_deleted')) else 'active_leads'
        bucket[key]+=int(row.get('total') or 0)
    for bucket in totals.values():
        req=max(0,int(bucket['requests']))
        active=int(bucket['active_opportunities'])+int(bucket['active_leads'])
        discarded=int(bucket['discarded_opportunities'])+int(bucket['discarded_leads'])
        kept_total=active+discarded
        bucket['active_records']=active; bucket['discarded_records']=discarded
        bucket['retention_rate']=(float(active)/kept_total) if kept_total else 0.0
        bucket['error_rate']=(float(bucket['errors'])/req) if req else 0.0
        bucket['unique_per_100']=(100.0*float(bucket['unique_results'])/req) if req else 0.0
        bucket['active_per_100']=(100.0*float(active)/req) if req else 0.0
        bucket['results_per_request']=(float(bucket['results'])/req) if req else 0.0
    return totals


def _adaptive_source_key(source, efficiency):
    stats=efficiency.get(getattr(source,'pk',None),{})
    req=int(stats.get('requests') or 0); unique=int(stats.get('unique_results') or 0)
    active=int(stats.get('active_records') or 0); discarded=int(stats.get('discarded_records') or 0)
    error_rate=float(stats.get('error_rate') or 0.0); unique_per_100=float(stats.get('unique_per_100') or 0.0)
    active_per_100=float(stats.get('active_per_100') or 0.0); retention=float(stats.get('retention_rate') or 0.0)
    # Productive retained sources lead. New/low-sample sources get an exploration tier.
    # Repeated zero-yield/high-error sources are demoted but never permanently disabled.
    if req >= 25 and error_rate >= 0.65:
        tier=3
    elif active == 0 and discarded >= 3:
        tier=2
    elif req >= 40 and unique == 0 and active == 0:
        tier=2
    elif active > 0:
        tier=0
    elif unique > 0:
        tier=1
    else:
        tier=1
    score=(active_per_100*12.0)+(unique_per_100*4.0)+(min(active,25)*2.0)+(retention*10.0)-min(40.0,error_rate*40.0)-min(20,discarded)*0.25
    return (tier,-score,-int(getattr(source,'priority',0) or 0),str(getattr(source,'name','')).casefold())



def _forum_source_cooldown(source, *, hours=6, threshold=2):
    """Classify Forum failures into cooldowns instead of treating every miss equally."""
    try:
        now=timezone.now(); cutoff=now-timedelta(hours=max(6,int(hours or 6)))
        rows=list(UsageMetric.objects.filter(
            category='fresh_source_result',provider=str(getattr(source,'name','') or ''),
            stage=FORUM_DIRECT_ADAPTER,at__gte=cutoff,
        ).order_by('-at')[:6])
        if not rows:
            return False,{'attempts':0}
        latest=rows[0]; err=str((latest.metadata or {}).get('error') or '').casefold()
        age=max(0,(now-latest.at).total_seconds())
        # Access-denied/rate-limit failures are immediately expensive and should cool.
        if int(latest.errors or 0)>0:
            if any(x in err for x in ('403','forbidden','access denied','challenge','captcha')):
                seconds=6*3600
                return age<seconds,{'attempts':len(rows),'cooldown_seconds':seconds,'class':'access_denied','last_attempt_at':latest.at.isoformat(),'last_error':err[:300]}
            if any(x in err for x in ('429','rate limit','too many requests','retry-after')):
                seconds=2*3600
                m=re.search(r'retry[- ]?after[^0-9]{0,12}(\d{1,6})',err)
                if m:
                    seconds=max(300,min(12*3600,int(m.group(1))))
                return age<seconds,{'attempts':len(rows),'cooldown_seconds':seconds,'class':'rate_limited','last_attempt_at':latest.at.isoformat(),'last_error':err[:300]}
        consecutive=0; parse_failures=0; network_failures=0
        for row in rows:
            row_err=str((row.metadata or {}).get('error') or '').casefold()
            if int(row.errors or 0)<=0 or int(row.pages or 0)>0:
                break
            consecutive+=1
            if any(x in row_err for x in ('parse','json','decode','selector','html structure')):
                parse_failures+=1
            if any(x in row_err for x in ('timeout','timed out','connection','network','dns','temporary')):
                network_failures+=1
        if parse_failures>=2:
            seconds=60*60
            return age<seconds,{'attempts':len(rows),'consecutive_failures':consecutive,'cooldown_seconds':seconds,'class':'parse','last_attempt_at':latest.at.isoformat(),'last_error':err[:300]}
        if network_failures>=3:
            seconds=20*60
            return age<seconds,{'attempts':len(rows),'consecutive_failures':consecutive,'cooldown_seconds':seconds,'class':'network','last_attempt_at':latest.at.isoformat(),'last_error':err[:300]}
        cooled=consecutive>=max(2,int(threshold or 2))
        return cooled,{'attempts':len(rows),'consecutive_failures':consecutive,'cooldown_seconds':30*60 if cooled else 0,'class':'repeated_error' if cooled else 'healthy','last_attempt_at':latest.at.isoformat(),'last_error':err[:300]}
    except Exception:
        return False,{}


def _source_last_attempt_map(sources):
    """Return the newest completed adapter-attempt timestamp per source name."""
    names=[str(getattr(source,'name','') or '') for source,_adapter in (sources or []) if str(getattr(source,'name','') or '')]
    if not names:
        return {}
    try:
        rows=UsageMetric.objects.filter(category='fresh_source_result',provider__in=names).values('provider').annotate(last_attempt=Max('at'))
        return {str(row.get('provider') or ''):row.get('last_attempt') for row in rows}
    except Exception:
        return {}


def _coverage_source_key(pair, last_attempts, efficiency):
    source,_adapter=pair
    at=(last_attempts or {}).get(str(getattr(source,'name','') or ''))
    try:
        stamp=float(at.timestamp()) if at is not None else -1.0
    except Exception:
        stamp=-1.0
    # Never-attempted and longest-idle sources come first. Adaptive rank/priority/name
    # only break ties; historical yield cannot permanently suppress an enabled source.
    return (0 if at is None else 1,stamp,_adaptive_source_key(source,efficiency))


def _select_direct_sources(sources, efficiency, last_attempts, cap_sources):
    """Split a bounded direct pass into performance and coverage capacity."""
    sources=list(sources or [])
    if not sources:
        return [],{}
    cap_sources=max(1,min(len(sources),int(cap_sources or 1)))
    if len(sources)<=cap_sources:
        return sources,{source.name:'within-cap' for source,_adapter in sources}

    coverage_slots=max(1,min(2,cap_sources//3 if cap_sources>=3 else 1))
    coverage_order=sorted(sources,key=lambda pair:_coverage_source_key(pair,last_attempts,efficiency))
    coverage=coverage_order[:coverage_slots]
    coverage_ids={getattr(source,'pk',None) for source,_adapter in coverage}
    performance_slots=max(0,cap_sources-len(coverage))
    healthy=[pair for pair in sources if _adaptive_source_key(pair[0],efficiency)[0] < 2 and getattr(pair[0],'pk',None) not in coverage_ids]
    performance=healthy[:performance_slots]
    chosen_ids=coverage_ids|{getattr(source,'pk',None) for source,_adapter in performance}
    if len(performance)<performance_slots:
        for pair in sources:
            source,_adapter=pair
            if getattr(source,'pk',None) in chosen_ids:
                continue
            performance.append(pair); chosen_ids.add(getattr(source,'pk',None))
            if len(performance)>=performance_slots:
                break

    selected=(coverage+performance)[:cap_sources]
    reasons={source.name:'coverage-oldest-attempt' for source,_adapter in coverage}
    reasons.update({source.name:'performance' for source,_adapter in performance})
    return selected,reasons


_INCREMENTAL_ATS_ADAPTERS={'greenhouse','lever','ashby','smartrecruiters'}


def _stable_candidate_url(value):
    value=str(value or '').strip()
    if not value:
        return ''
    try:
        parts=urllib.parse.urlsplit(value)
        if not parts.scheme or not parts.netloc:
            return value.rstrip('/').casefold()
        host=(parts.hostname or '').casefold().removeprefix('www.')
        port=(':'+str(parts.port)) if parts.port and parts.port not in {80,443} else ''
        path=(parts.path or '/').rstrip('/') or '/'
        query=('?'+parts.query) if parts.query else ''
        return f'{parts.scheme.casefold()}://{host}{port}{path}{query}'
    except Exception:
        return value.rstrip('/').casefold()


def _remove_known_opportunity_urls(rows):
    """Skip exact URLs already retained before ATS candidates reach page fetch/AI stages."""
    rows=list(rows or [])
    raw=[str((row or {}).get('url') or '').strip() for row in rows]
    lookup=list(dict.fromkeys(x for url in raw for x in (url,url.rstrip('/')) if x))[:500]
    if not lookup:
        return rows,0
    try:
        known=set()
        qs=Opportunity.objects.filter(Q(url__in=lookup)|Q(target_url__in=lookup)|Q(canonical_url__in=lookup)).values_list('url','target_url','canonical_url')
        for triple in qs:
            for value in triple:
                normalized=_stable_candidate_url(value)
                if normalized:
                    known.add(normalized)
        if not known:
            return rows,0
        fresh=[]; skipped=0
        for row in rows:
            if _stable_candidate_url((row or {}).get('url')) in known:
                skipped+=1
            else:
                fresh.append(row)
        return fresh,skipped
    except Exception:
        return rows,0


def direct_source_rows(campaign, search_profile=None, *, limit=60, test=False, source_type=None, include_forums=True, progress_callback=None, should_stop=None, stage_budget_seconds=None, max_sources=None):
    """Return cheap-prefiltered direct candidates with their SearchSource objects.

    Output rows use the same wrapper shape as discovery.raw_records:
    ``{'result': result, 'source': SearchSource, 'query': description}``.

    ``source_type`` lets the campaign runner give forum browsing its own bounded
    stage.  That keeps marketplace/listing-page forum acquisition visible and
    prevents it from being mixed into, capped by, or hidden behind the ordinary
    fresh/direct-source pass.  ``include_forums=False`` preserves the pre-0.10.66
    behavior for non-forum direct adapters after the dedicated forum pass runs.
    """
    if not campaign: return [],[],{}
    explicit=set(str(x) for x in (getattr(campaign,'source_names',None) or []) if str(x).strip())
    qs=SearchSource.objects.filter(enabled=True).exclude(source_type='cloud_ai')
    if source_type:
        qs=qs.filter(source_type=str(source_type))
    elif not include_forums:
        qs=qs.exclude(source_type='forum')
    if explicit: qs=qs.filter(name__in=explicit)
    adapter_sources=[]
    for source in qs.order_by('-priority','category','name'):
        cfg=source.config_json if isinstance(source.config_json,dict) else {}
        adapter=str(cfg.get('direct_adapter') or '').strip().lower()
        if adapter in ADAPTER_FUNCTIONS:
            adapter_sources.append((source,adapter))
    # Credential-dependent adapters must not consume one of the bounded direct execution
    # slots when they cannot run. They remain in search_fallback_sources because ordinary
    # search-engine discovery is still valid for their public domains.
    skipped_unconfigured=[source.name for source,adapter in adapter_sources if not _adapter_configured(source,adapter)]
    search_fallback_sources=list(adapter_sources)
    sources=[pair for pair in adapter_sources if _adapter_configured(pair[0],pair[1])]
    efficiency=_source_efficiency_map(sources,days=7)
    sources.sort(key=lambda pair:_adaptive_source_key(pair[0],efficiency))
    available_sources=list(sources)
    last_attempts=_source_last_attempt_map(available_sources)
    selection_reason={}
    forum_rotation_offset=None
    forum_cooled_sources={}
    if str(source_type or '').lower()=='forum' and sources:
        healthy=[]; cooled=[]
        for pair in sources:
            is_cooled,details=_forum_source_cooldown(pair[0],hours=3,threshold=2)
            if is_cooled:
                forum_cooled_sources[pair[0].name]=details; cooled.append(pair)
            else:
                healthy.append(pair)
        # Normally skip recently broken sources. If every Forum source is cooling down,
        # keep one rotating recovery probe so the set can recover automatically.
        if healthy:
            sources=healthy
        elif cooled:
            try:
                recovery_offset=(int(timezone.now().timestamp()//3600)+int(getattr(campaign,'pk',0) or 0)) % len(cooled)
            except Exception:
                recovery_offset=0
            sources=[cooled[recovery_offset]]
    if max_sources is not None and sources:
        cap_sources=max(1,min(len(sources),int(max_sources or 1)))
        if str(source_type or '').lower()=='forum':
            # Forum passes may try a few sources inside one bounded HTTP budget, but still
            # rotate every five minutes. A source only stops the pass after producing useful candidates.
            try:
                bucket=int(timezone.now().timestamp()//300)
                forum_rotation_offset=(bucket+int(getattr(campaign,'pk',0) or 0)) % len(sources)
            except Exception:
                forum_rotation_offset=0
            ordered=sources[forum_rotation_offset:]+sources[:forum_rotation_offset]
            sources=ordered[:cap_sources]
        else:
            # Reserve roughly one third of the bounded direct slots (two of the default
            # six) for the longest-idle configured sources. Coverage candidates execute
            # first so the stage wall-clock budget cannot repeatedly expire behind leaders.
            sources,selection_reason=_select_direct_sources(sources,efficiency,last_attempts,cap_sources)
    terms=_campaign_terms(campaign,search_profile)
    wrapped=[]; errors=[]; counts=Counter(); raw_counts=Counter(); skipped_known_counts=Counter(); attempted_names=[]
    per_source=max(8,min(40,int(limit or 60)//max(1,len(sources)) + 6))
    if test: per_source=min(per_source,10)
    stage_started=time.monotonic()
    if stage_budget_seconds is None:
        try:
            stage_budget_seconds=max(10,min(25,int(os.environ.get('SCOUTBOX_FORUM_BROWSE_STAGE_MAX_SECONDS','25') or 25))) if str(source_type or '').lower()=='forum' else 0
        except Exception:
            stage_budget_seconds=25 if str(source_type or '').lower()=='forum' else 0
    else:
        try:
            stage_budget_seconds=max(0,min(1800,int(stage_budget_seconds or 0)))
        except Exception:
            stage_budget_seconds=0
    total_sources=len(sources)
    for source_index,(source,adapter) in enumerate(sources,1):
        if should_stop and should_stop():
            break
        if stage_budget_seconds and time.monotonic()-stage_started>stage_budget_seconds:
            errors.append(f'{"Forum browsing" if str(source_type or "").lower()=="forum" else "Direct-source"} time budget reached after {source_index-1}/{total_sources} sources; remaining sources will rotate into later runs.')
            break
        if not _adapter_configured(source,adapter):
            skipped_unconfigured.append(source.name)
            continue
        attempted_names.append(source.name)
        adapter_started=timezone.now()
        progress_value=(11+int(4*source_index/max(1,total_sources))) if str(source_type or '').lower()=='forum' else None
        progress_message=(f'Browsing forum sources: {source.name} ({source_index}/{total_sources})' if str(source_type or '').lower()=='forum' else None)
        try:
            rows,err=_run_adapter_with_liveness(source,adapter,ADAPTER_FUNCTIONS[adapter],campaign,search_profile,per_source,progress_callback=progress_callback,should_stop=should_stop,progress_value=progress_value,progress_message=progress_message)
        except Exception as exc:
            rows=[]; err=str(exc); _adapter_exception_metric(source,adapter,exc)
        raw_counts[source.name]+=len(rows or [])
        _adapter_result_metric(source,adapter,len(rows or []),started_at=adapter_started,error=err,selection_reason=selection_reason.get(source.name,''))
        if err: errors.append(f'{source.name}: {err}')
        if adapter in _INCREMENTAL_ATS_ADAPTERS:
            rows,known_skipped=_remove_known_opportunity_urls(rows or [])
            skipped_known_counts[source.name]+=int(known_skipped or 0)
        accepted=[]
        for row in rows or []:
            if _keep_candidate(row,campaign,terms): accepted.append(row)
        accepted.sort(key=lambda r:(-_score_candidate(r,terms), -(_parse_date(r.get('published_at')).timestamp() if _parse_date(r.get('published_at')) else 0)))
        for row in accepted[:per_source]:
            row['_provenance']=[{
                'source':source.name,'query':'Fresh Source Discovery · '+adapter,'url':row.get('url',''),
                'acquisition_path':row.get('_acquisition_path','Direct source'),'direct_adapter':adapter,
                'source_item_id':row.get('_direct_item_id',''),'published_at':row.get('published_at',''),
                'source_category':('forum' if row.get('_forum_source') else ''),
                'forum_post_id':row.get('_forum_post_id',''),'forum_post_date':row.get('_forum_post_date',''),
            }]
            wrapped.append({'result':row,'source':source,'query':'Fresh Source Discovery · '+source.name})
            counts[source.name]+=1
        if str(source_type or '').lower()=='forum' and accepted:
            # A HTTP 200 with zero useful candidates is not a productive Forum pass.
            # Continue through the bounded source set until useful material appears or
            # the source/time budget is exhausted.
            break
    # Global pre-AI cap prevents a large direct catalog from overwhelming local/cloud AI,
    # but every attempted ordinary direct source gets a small qualification floor first.
    # Without this second fairness layer, a source such as YC can be searched successfully
    # and return 60+ vacancies yet contribute zero candidates because another large catalog
    # wins every slot in the global prefilter sort.
    wrapped.sort(key=lambda rec:(-int((rec.get('result') or {}).get('_fresh_prefilter_score') or 0), -(_parse_date((rec.get('result') or {}).get('published_at')).timestamp() if _parse_date((rec.get('result') or {}).get('published_at')) else 0)))
    cap=min(120,max(10,int(limit or 60)))
    selected_wrapped=[]; qualification_floor_by_source={}
    if str(source_type or '').lower()!='forum' and wrapped and len(sources)>1:
        reserve_each=max(1,min(3,cap//max(1,len(sources)*3)))
        selected_keys=set()
        for source,_adapter in sources:
            source_rows=[rec for rec in wrapped if getattr(rec.get('source'),'pk',None)==getattr(source,'pk',None)]
            take=source_rows[:reserve_each]
            qualification_floor_by_source[source.name]=len(take)
            for rec in take:
                key=(getattr(rec.get('source'),'pk',None),_direct_row_dedupe_key(rec.get('result') or {}))
                if key in selected_keys or len(selected_wrapped)>=cap:
                    continue
                selected_keys.add(key); selected_wrapped.append(rec)
        for rec in wrapped:
            key=(getattr(rec.get('source'),'pk',None),_direct_row_dedupe_key(rec.get('result') or {}))
            if key in selected_keys:
                continue
            selected_keys.add(key); selected_wrapped.append(rec)
            if len(selected_wrapped)>=cap:
                break
    else:
        selected_wrapped=wrapped[:cap]
    qualification_selected_by_source=Counter(getattr(rec.get('source'),'name','') for rec in selected_wrapped)
    efficiency_meta={}
    for source,_adapter in available_sources:
        stats=efficiency.get(getattr(source,'pk',None),{})
        efficiency_meta[source.name]={
            'requests_7d':int(stats.get('requests') or 0),'unique_7d':int(stats.get('unique_results') or 0),
            'active_records_7d':int(stats.get('active_records') or 0),'discarded_records_7d':int(stats.get('discarded_records') or 0),
            'retention_rate_7d':round(float(stats.get('retention_rate') or 0.0),4),
            'errors_7d':int(stats.get('errors') or 0),'error_rate_7d':round(float(stats.get('error_rate') or 0.0),4),
            'unique_per_100_requests_7d':round(float(stats.get('unique_per_100') or 0.0),3),
        }
    return selected_wrapped,errors,{
        'sources':[s.name for s,_ in sources],
        'available_sources':[s.name for s,_ in available_sources],
        'search_fallback_sources':[s.name for s,_ in search_fallback_sources],
        'configured_sources':[s.name for s,_ in available_sources],
        'skipped_unconfigured':skipped_unconfigured,
        'selection_reason':selection_reason,
        'last_attempt_at':{name:(value.isoformat() if value else '') for name,value in last_attempts.items()},
        'forum_rotation_offset':forum_rotation_offset,'raw_by_source':dict(raw_counts),'accepted_by_source':dict(counts),
        'known_opportunity_urls_skipped_by_source':dict(skipped_known_counts),'known_opportunity_urls_skipped':sum(skipped_known_counts.values()),
        'raw_direct_candidates':sum(raw_counts.values()),'prefiltered_candidates':len(selected_wrapped),'qualification_floor_by_source':qualification_floor_by_source,
        'qualification_selected_by_source':dict(qualification_selected_by_source),
        'qualification_dropped_by_source':{name:max(0,int(counts.get(name,0))-int(qualification_selected_by_source.get(name,0))) for name in counts},
        'source_type_filter':str(source_type or ''),'include_forums':bool(include_forums),
        'stage_time_budget_seconds':stage_budget_seconds,'source_limit':int(max_sources or 0),
        'sources_attempted':len(attempted_names),'attempted_sources':attempted_names,
        'source_efficiency_7d':efficiency_meta,'cooled_sources':forum_cooled_sources,
    }


def forum_source_rows(campaign, search_profile=None, *, limit=60, test=False, progress_callback=None, should_stop=None, stage_budget_seconds=None, max_sources=None):
    """Run only Forum sources under non-bypassable throughput safety caps.

    Forum acquisition is supplementary. The scheduler normally supplies these limits,
    but this public helper clamps them again so a manual/test/future caller cannot turn a
    Forum pass back into a multi-source, long-running workload.
    """
    try:
        hard_budget=max(10,min(25,int(os.environ.get('SCOUTBOX_FORUM_ONLY_STAGE_MAX_SECONDS','25') or 25)))
    except Exception:
        hard_budget=25
    try:
        requested_budget=hard_budget if stage_budget_seconds is None else max(1,int(stage_budget_seconds))
    except Exception:
        requested_budget=hard_budget
    effective_budget=min(hard_budget,requested_budget)
    try:
        requested_sources=3 if max_sources is None else max(1,int(max_sources or 1))
    except Exception:
        requested_sources=3
    effective_sources=min(3,requested_sources)
    return direct_source_rows(
        campaign, search_profile, limit=limit, test=test, source_type='forum',
        progress_callback=progress_callback, should_stop=should_stop,
        stage_budget_seconds=effective_budget, max_sources=effective_sources,
    )


def non_forum_direct_source_rows(campaign, search_profile=None, *, limit=60, test=False, progress_callback=None, should_stop=None, stage_budget_seconds=None, max_sources=None):
    """Run direct adapters other than Forum sources."""
    return direct_source_rows(campaign, search_profile, limit=limit, test=test, include_forums=False, progress_callback=progress_callback, should_stop=should_stop, stage_budget_seconds=stage_budget_seconds, max_sources=max_sources)
