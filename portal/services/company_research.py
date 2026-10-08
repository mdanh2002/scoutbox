import json
import hashlib
import re
import requests
from urllib.parse import urlsplit, urlunsplit
from django.utils import timezone
from portal.models import SearchSource, CompanyResearchCache, PortalSettings
from .search import search_source, ACTIVE_PROVIDER_NAMES, is_search_engine_url
from .ai import generate, generate_with, generate_with_route, route_for_stage, effective_route_for_stage, web_search_with, configured_cloud_web_routes, LocalAILaneBusy
from .presentation import clean_placeholder
from .pagefetch import fetch_target
from .cloud_budget import is_cloud_provider, scoped_usage_context
from .platforms import is_job_platform_host as _shared_job_platform_host, is_platform_company_name as _shared_platform_company_name
from .location_values import strip_non_company_location_items, legacy_location_text


# 0.10.90: platform identity is centralized in services.platforms.  Keep these
# wrappers because other modules import them from company_research.
def _job_or_platform_host(host):
    return _shared_job_platform_host(host)

def is_job_or_platform_host(host):
    return _shared_job_platform_host(host)

def _company_label_key(value):
    text=str(value or '').casefold()
    text=re.sub(r'(?i)\b(?:inc|llc|ltd|limited|corp|corporation|company|co|gmbh|plc|pty|group|holdings)\b',' ',text)
    return re.sub(r'[^a-z0-9]+',' ',text).strip()

def is_job_or_platform_company_name(value):
    return _shared_platform_company_name(value)

def _clean_research_company_name(value):
    company=clean_placeholder(value)
    return '' if is_job_or_platform_company_name(company) else company

_FREE_EMAIL_HOSTS=(
    'gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com','icloud.com','proton.me','protonmail.com','aol.com',
)
_TWO_PART_SUFFIXES={'co.uk','org.uk','com.au','net.au','co.nz','com.sg','com.my','co.jp','co.in','com.br','com.mx','co.za'}
_RDAP_BOOTSTRAP_CACHE={'loaded_at':None,'services':{}}
_RDAP_BOOTSTRAP_TTL_SECONDS=24*60*60

def _registrable_domain(host):
    host=str(host or '').lower().strip('.').removeprefix('www.')
    if not host: return ''
    labels=[x for x in host.split('.') if x]
    if len(labels)<=2: return host
    tail='.'.join(labels[-2:])
    return '.'.join(labels[-3:]) if tail in _TWO_PART_SUFFIXES else tail

def _company_name_tokens(value):
    if is_job_or_platform_company_name(value):
        return []
    stop={'inc','llc','ltd','limited','corp','corporation','company','co','gmbh','plc','pty','group','holdings','technologies','technology','systems','solutions','network','networks'}
    return [x for x in re.findall(r'[a-z0-9]+',str(value or '').casefold()) if len(x)>=3 and x not in stop]


def _company_identity_key(value):
    """Compact company identity key used only for deterministic cache/domain matching."""
    tokens=_company_name_tokens(value)
    if tokens:
        return ''.join(tokens)
    return re.sub(r'[^a-z0-9]+','',_company_label_key(value))


def _company_lookup_variants(value):
    """Exact-query variants that bridge harmless spelling/spacing differences.

    In particular, ExtraHop and Extra Hop should share deterministic company-domain
    evidence without broad fuzzy matching across unrelated companies.
    """
    raw=' '.join(str(value or '').split()).strip()
    label=' '.join(_company_label_key(raw).split()).strip()
    compact=_company_identity_key(raw)
    values=[]
    for item in (raw,label,raw.replace(' ',''),label.replace(' ',''),compact):
        item=str(item or '').strip()
        if item and item.casefold() not in {x.casefold() for x in values}:
            values.append(item)
    return values


def _domain_company_match_score(company, domain):
    """Return a positive score only when a domain visibly matches the company identity.

    The older partial-token rule accepted ``extra.com`` for ``Extra Hop`` because one
    token matched.  For multi-token/compound brands we require the compact full identity,
    all significant tokens, or a very close stem match.  This intentionally prefers
    unknown over attaching a registration date from the wrong domain.
    """
    domain=_registrable_domain(domain)
    stem=re.sub(r'[^a-z0-9]','',domain.split('.')[0].casefold()) if domain else ''
    key=_company_identity_key(company)
    tokens=[re.sub(r'[^a-z0-9]','',x) for x in _company_name_tokens(company)]
    tokens=[x for x in tokens if x]
    if not stem or not key:
        return 0
    if stem==key:
        return 10
    if len(tokens)>1 and all(token in stem for token in tokens):
        return 8
    if key in stem and len(key)>=4 and len(key)/max(1,len(stem))>=0.70:
        return 7
    if stem in key and len(stem)>=4 and len(stem)/max(1,len(key))>=0.75:
        return 6
    if len(tokens)==1:
        token=tokens[0]
        if token in stem and min(len(token),len(stem))/max(len(token),len(stem))>=0.75:
            return 5
    return 0


def _company_domain(entity, result=None):
    """Choose a company-controlled domain; never use a job board/ATS as company age."""
    company=_clean_research_company_name((result or {}).get('company') or getattr(entity,'company','') or '')
    if not company:
        return ''
    tokens=_company_name_tokens(company)
    candidates=[]
    def add(url,score):
        host=_host(url); domain=_registrable_domain(host)
        if not domain or _job_or_platform_host(domain): return
        if domain in _FREE_EMAIL_HOSTS: return
        match_score=_domain_company_match_score(company,domain) if tokens else 0
        candidates.append((score+match_score,domain,bool(match_score)))
    email=str(getattr(entity,'contact_email','') or getattr(entity,'email','') or '').strip().lower()
    if '@' in email: add('https://'+email.rsplit('@',1)[1],10)
    intel=result if isinstance(result,dict) else (getattr(entity,'company_intel',{}) or {})
    # Reuse an already verified domain for the same normalized company before falling
    # back to role/source URLs. This is especially important for aggregator-only rows:
    # one Mirantis record with mirantis.com should repair its sibling Mirantis rows.
    try:
        seen_cache=set()
        for company_variant in _company_lookup_variants(company):
            for cached in CompanyResearchCache.objects.filter(company__iexact=company_variant).order_by('-researched_at')[:4]:
                if cached.pk in seen_cache:
                    continue
                seen_cache.add(cached.pk)
                if cached.domain:
                    add('https://'+str(cached.domain).strip(),12)
    except Exception:
        pass
    if isinstance(intel,dict):
        structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
        # Company research may already know the official site even when the vacancy came
        # from an ATS/aggregator. Those deterministic fields are stronger than the job URL.
        for key,score in (('website',11),('company_website',11),('company_domain',11),('domain_age_domain',10),('domain',10)):
            raw=structured.get(key) or intel.get(key)
            if raw:
                value=str(raw).strip()
                add(value if '://' in value else 'https://'+value,score)
        for fact in intel.get('facts') or []:
            if not isinstance(fact,dict):
                continue
            label=str(fact.get('label') or '').strip().casefold()
            if label in {'domain','website','company website','official website','homepage','home page'}:
                raw=str(fact.get('value') or '').strip()
                if raw:
                    add(raw if '://' in raw else 'https://'+raw,10)
        for row in intel.get('sources') or []:
            if isinstance(row,dict): add(row.get('url'),8 if 'official' in str(row.get('title') or '').casefold() else 6)
            else: add(row,5)
    for name,score in (('target_url',5),('url',5),('source_url',4),('contact_url',6)):
        add(getattr(entity,name,''),score)
    if not candidates: return ''
    # When the company name is known, an unrelated recruiter/contact domain is not enough.
    # Prefer false-negative/unknown over assigning the age of an agency or infrastructure
    # provider to the employer. Company-name-free records may still use the strongest
    # non-platform domain because there is no name anchor to compare against.
    if tokens:
        candidates=[row for row in candidates if row[2]]
        if not candidates: return ''
    candidates.sort(key=lambda x:(x[0],-len(x[1])),reverse=True)
    return candidates[0][1]


def company_domain_for_entity(entity, result=None):
    """Return the best plausible company-controlled registrable domain for an entity."""
    return _company_domain(entity,result)


def _discover_company_domain_from_search(entity, result=None):
    """Resolve an official-looking company domain from a tiny bounded public search.

    This is used only by deterministic Domain/RDAP maintenance when Company Research has
    already resolved the company identity but retained no usable official-domain evidence.
    It never invokes Local or Cloud AI and never accepts job boards/ATS hosts.  A result is
    accepted only when the registrable domain itself strongly matches the normalized company
    name, which intentionally prefers an unresolved domain over an unrelated recruiter/site.
    """
    company=_clean_research_company_name((result or {}).get('company') or getattr(entity,'company','') or '')
    if not company:
        return ''
    tokens=_company_name_tokens(company)
    compact_company=''.join(tokens)
    if len(compact_company)<4:
        return ''
    candidates=[]
    query=f'"{company}" official website'
    for provider in _providers(limit=2):
        try:
            rows,err=search_source(provider,query,limit=5,usage_category='company_research')
        except Exception:
            continue
        if err:
            continue
        for position,row in enumerate(rows[:5]):
            if not isinstance(row,dict):
                continue
            url=str(row.get('url') or '').strip()
            host=_host(url); domain=_registrable_domain(host)
            if not domain or _job_or_platform_host(domain) or domain in _FREE_EMAIL_HOSTS or is_search_engine_url(url):
                continue
            match_score=_domain_company_match_score(company,domain)
            if not match_score:
                continue
            title=' '.join(str(row.get('title') or '').casefold().split())
            snippet=' '.join(str(row.get('snippet') or '').casefold().split())
            score=22+match_score
            score+=max(0,5-position)
            if 'official' in title or 'official' in snippet: score+=4
            label_key=_company_label_key(company)
            if label_key and label_key in _company_label_key(title): score+=5
            candidates.append((score,domain))
        if candidates:
            break
    if not candidates:
        return ''
    candidates.sort(key=lambda x:(x[0],-len(x[1])),reverse=True)
    return candidates[0][1]


def _providers(limit=4):
    # Use every enabled v1 web adapter. Older databases can retain a non-active label
    # even though the adapter is available, so adapter_status is not a hard gate here.
    return list(SearchSource.objects.filter(enabled=True,name__in=ACTIVE_PROVIDER_NAMES).order_by('-priority','name')[:limit])


def _host(url):
    try: return (urlsplit(str(url or '')).hostname or '').lower().removeprefix('www.')
    except Exception: return ''


def _first_party_candidate(url):
    host=_host(url)
    if not host or is_search_engine_url(url): return False
    return not _job_or_platform_host(host)



def _company_from_url(url):
    """Best-effort company label from a first-party hostname when metadata is blank."""
    host=_host(url)
    if not host or _job_or_platform_host(host): return ''
    labels=[x for x in host.split('.') if x]
    while len(labels)>2 and labels[0] in {'www','jobs','job','careers','career','work','hiring','recruiting','recruitment'}:
        labels=labels[1:]
    two_part_suffixes={'co.uk','org.uk','com.au','net.au','co.nz','com.sg','com.my','co.jp','co.in','com.br','com.mx','co.za'}
    tail='.'.join(labels[-2:]) if len(labels)>=2 else ''
    base=labels[-3] if len(labels)>=3 and tail in two_part_suffixes else (labels[-2] if len(labels)>=2 else labels[0])
    return re.sub(r'[-_]+',' ',base).strip().title()

def _root_url(url):
    try:
        p=urlsplit(url)
        if p.scheme in ('http','https') and p.netloc:
            return urlunsplit((p.scheme,p.netloc,'/','',''))
    except Exception:
        pass
    return ''


def _baseline(entity, company, country):
    facts=[{'label':'Company','value':company}]
    if country: facts.append({'label':'Location','value':country})
    return {
        'company':company,'confidence':25 if country else 20,'facts':facts,'sources':[],
        'errors':[],'status':'collecting','updated_at':timezone.now().isoformat(),
    }


def _entity_url(entity):
    return str(getattr(entity,'target_url','') or getattr(entity,'url','') or getattr(entity,'source_url','') or '').strip()


def _entity_text(entity):
    return str(getattr(entity,'description','') or getattr(entity,'raw_search_snippet','') or getattr(entity,'evidence','') or getattr(entity,'match_summary','') or getattr(entity,'company_summary','') or getattr(entity,'notes','') or '').strip()


def _entity_title(entity):
    return str(getattr(entity,'title','') or getattr(entity,'company','') or 'Company').strip()


def _entity_subject_type(entity):
    name=entity.__class__.__name__.lower()
    if name=='companylead': return 'hidden_lead'
    if name=='contact': return 'contact'
    return 'opportunity'


def company_summary_from_intel(intel, max_chars=600):
    """Build a brief source-backed company summary from collected Company Info facts."""
    if not isinstance(intel,dict): return ''
    preferred=[]; secondary=[]
    for row in intel.get('facts') or []:
        if not isinstance(row,dict): continue
        label=str(row.get('label') or '').strip().casefold(); value=' '.join(str(row.get('value') or '').split()).strip()
        if not value: continue
        if label in {'what they do','products/technology','products and technology','products','technology'}:
            preferred.append(value)
        elif label in {'actionability','potential work paths','engagement'}:
            secondary.append(value)
    parts=[]
    for value in preferred+secondary:
        if value.casefold() not in {x.casefold() for x in parts}: parts.append(value)
        if len(parts)>=2: break
    text=' '.join(parts).strip()
    if not text: return ''
    if len(text)>max_chars:
        text=text[:max_chars].rsplit(' ',1)[0].rstrip(' ,;:-')+'…'
    return text


def stored_company_context(company='', email='', source_url=''):
    """Return the strongest already-collected company context for a contact/record.

    Uses exact originating URL/email/company matches first, then the company-domain cache.
    No network or AI calls are made.
    """
    from django.db.models import Q
    from portal.models import Opportunity, CompanyLead, Contact
    company=' '.join(str(company or '').split()).strip()
    email=str(email or '').strip().lower(); source_url=str(source_url or '').strip()
    candidates=[]
    def add(intel, summary=''):
        if not isinstance(intel,dict) or not intel: return
        score=(100 if company_info_has_display_data(intel) else 0)+min(60,len(intel.get('facts') or [])*5)+min(20,len(intel.get('sources') or [])*2)
        try: score+=int(intel.get('confidence') or 0)//5
        except Exception: pass
        candidates.append((score,summary or company_summary_from_intel(intel,1200),intel))
    q=Q()
    if company: q|=Q(company__iexact=company)
    if email: q|=Q(contact_email__iexact=email)
    if source_url:
        q|=Q(target_url=source_url)|Q(url=source_url)|Q(search_url=source_url)|Q(canonical_url=source_url)
    if q.children:
        for row in Opportunity.objects.filter(q,user_deleted=False,suppressed=False).order_by('-last_seen')[:12]:
            add(row.company_intel)
        lq=Q()
        if company: lq|=Q(company__iexact=company)
        if email: lq|=Q(contact_email__iexact=email)
        if source_url: lq|=Q(target_url=source_url)|Q(source_url=source_url)|Q(search_url=source_url)
        for row in CompanyLead.objects.filter(lq,user_deleted=False,deleted_at__isnull=True).order_by('-updated_at')[:12]:
            add(row.company_intel,' '.join(str(row.summary or '').split()).strip()[:1200])
        cq=Q()
        if company: cq|=Q(company__iexact=company)
        if email: cq|=Q(email__iexact=email)
        if source_url: cq|=Q(source_url=source_url)
        if cq.children:
            for row in Contact.objects.filter(cq,deleted_at__isnull=True).order_by('-updated_at')[:12]:
                add(row.company_intel,' '.join(str(row.company_summary or '').split()).strip()[:1200])
    domain=''
    if email and '@' in email: domain=_registrable_domain(email.rsplit('@',1)[1])
    if not domain and source_url: domain=_registrable_domain(_host(source_url))
    if domain and not _job_or_platform_host(domain) and domain not in _FREE_EMAIL_HOSTS:
        cache=CompanyResearchCache.objects.filter(domain=domain).order_by('-researched_at').first()
        if cache: add(cache.data if isinstance(cache.data,dict) else {})
    if not candidates: return '',{}
    candidates.sort(key=lambda x:x[0],reverse=True)
    return (candidates[0][1] or '')[:1200], candidates[0][2]


def _employee_size_band(n):
    """Return a deliberately coarse employee-size band for dense list display/storage."""
    try: n=max(0,int(n or 0))
    except Exception: return ''
    if n<=0: return ''
    if n<=10: return '1–10'
    if n<=20: return '10–20'
    if n<=50: return '20–50'
    if n<=100: return '50–100'
    if n<=250: return '100–250'
    if n<=500: return '250–500'
    if n<=1000: return '500–1,000'
    return '1,000+'


def _employee_number(raw):
    text=str(raw or '').strip().lower()
    if not text: return 0
    text=re.sub(r'(?<=\d),(?=\d)','',text)
    m=re.search(r'(?<!\d)(\d+(?:\.\d+)?)\s*(k|thousand|m|million)?(?!\w)',text,re.I)
    if not m: return 0
    value=float(m.group(1)); suffix=(m.group(2) or '').lower()
    if suffix in {'k','thousand'}: value*=1000
    elif suffix in {'m','million'}: value*=1000000
    return int(round(value))


def _normalise_employee_size(value):
    """Normalize exact/range headcounts into coarse bands; never retain exact employee counts."""
    text=re.sub(r'\s+',' ',str(value or '')).strip()
    if not text: return ''
    clean=re.sub(r'(?<=\d),(?=\d)','',text)
    # Prefer the upper end of a supplied range because it avoids understating company size.
    m=re.search(r'(?<!\d)(\d+(?:\.\d+)?)\s*(k|thousand|m|million)?\s*(?:[–—-]|to)\s*(\d+(?:\.\d+)?)\s*(k|thousand|m|million)?(?!\w)',clean,re.I)
    if m:
        left=_employee_number((m.group(1) or '')+(m.group(2) or ''))
        right=_employee_number((m.group(3) or '')+(m.group(4) or ''))
        n=max(left,right)
        return _employee_size_band(n)
    n=_employee_number(clean)
    return _employee_size_band(n)


def _rdap_bootstrap_services():
    """Return an IANA TLD -> authoritative RDAP base mapping with a small cache."""
    now=timezone.now()
    loaded=_RDAP_BOOTSTRAP_CACHE.get('loaded_at')
    services=_RDAP_BOOTSTRAP_CACHE.get('services') or {}
    if loaded and services:
        try:
            if (now-loaded).total_seconds() < _RDAP_BOOTSTRAP_TTL_SECONDS:
                return services
        except Exception:
            pass
    response=requests.get(
        'https://data.iana.org/rdap/dns.json', timeout=6,
        headers={'Accept':'application/json','User-Agent':'ScoutBox/0.10.103'},
    )
    response.raise_for_status()
    data=response.json() if response.content else {}
    resolved={}
    for row in data.get('services') or []:
        if not isinstance(row,list) or len(row)<2: continue
        tlds=row[0] if isinstance(row[0],list) else []
        urls=row[1] if isinstance(row[1],list) else []
        base=next((str(x or '').strip() for x in urls if str(x or '').strip().startswith('https://')), '')
        if not base:
            base=next((str(x or '').strip() for x in urls if str(x or '').strip().startswith('http://')), '')
        if not base: continue
        for tld in tlds:
            key=str(tld or '').strip().lower().lstrip('.')
            if key: resolved[key]=base.rstrip('/')+'/'
    _RDAP_BOOTSTRAP_CACHE.update({'loaded_at':now,'services':resolved})
    return resolved


def _rdap_registration_event(data):
    """Extract a true creation/registration event; never substitute last-changed dates."""
    for row in (data or {}).get('events') or []:
        if not isinstance(row,dict): continue
        action=str(row.get('eventAction') or '').strip().casefold().replace('_',' ').replace('-',' ')
        if action in {'registration','registered','creation','created','domain registration','domain created'} and row.get('eventDate'):
            return str(row.get('eventDate') or '').strip()
    return ''


def _rdap_lookup(domain):
    """Query the authoritative registry selected from IANA's RDAP bootstrap.

    The public rdap.org aggregator is retained only as a bounded compatibility fallback
    when bootstrap discovery itself is unavailable or has no endpoint for the TLD.
    """
    tld=str(domain or '').rsplit('.',1)[-1].strip().lower()
    endpoint=''; source='iana_authoritative_rdap'; bootstrap_error=''
    try:
        endpoint=(_rdap_bootstrap_services().get(tld) or '').rstrip('/')
    except Exception as exc:
        bootstrap_error=str(exc)[:300]
    candidates=[]
    if endpoint:
        candidates.append((endpoint+'/domain/'+domain,source))
    else:
        candidates.append(('https://rdap.org/domain/'+domain,'rdap.org_fallback'))
    last={}
    for url,source_name in candidates:
        try:
            response=requests.get(
                url,timeout=7,allow_redirects=True,
                headers={'Accept':'application/rdap+json, application/json','User-Agent':'ScoutBox/0.10.103'},
            )
            status=int(response.status_code or 0)
            if 200 <= status < 300:
                return {'ok':True,'data':response.json() if response.content else {},'endpoint':url,
                        'source':source_name,'status':status,'transient':False,'error':''}
            transient=status in {408,425,429} or status>=500
            last={'ok':False,'data':{},'endpoint':url,'source':source_name,'status':status,
                  'transient':transient,'error':f'RDAP HTTP {status}'}
        except (requests.Timeout,requests.ConnectionError) as exc:
            last={'ok':False,'data':{},'endpoint':url,'source':source_name,'status':0,
                  'transient':True,'error':str(exc)[:300] or 'RDAP network timeout'}
        except Exception as exc:
            last={'ok':False,'data':{},'endpoint':url,'source':source_name,'status':0,
                  'transient':True,'error':str(exc)[:300]}
    if not last:
        last={'ok':False,'data':{},'endpoint':'','source':'iana_authoritative_rdap','status':0,
              'transient':True,'error':bootstrap_error or 'No RDAP endpoint available'}
    elif bootstrap_error:
        last['error']=(str(last.get('error') or '')+'; IANA bootstrap: '+bootstrap_error).strip('; ')[:500]
    return last


def _domain_age_fallback(entity, result):
    """Resolve/store registration age for a defensible company-controlled domain.

    This is deterministic network enrichment, not AI research. A known official domain is
    stored even when RDAP is temporarily unavailable so the list tooltip can still show
    ``Domain: …`` with ``Domain age: Unknown`` and a later maintenance pass can retry.
    """
    structured=dict(result.get('structured') or {}) if isinstance(result.get('structured'),dict) else {}
    domain=_company_domain(entity,result)
    facts=[dict(x) for x in (result.get('facts') or []) if isinstance(x,dict) and str(x.get('label') or '').casefold()!='domain age']
    if not domain:
        for key in (
            'domain_registered_at','domain_age_years','domain_age_label','domain_age_domain',
            'domain_age_source','domain_age_endpoint','domain_age_error','domain_age_unavailable_reason',
        ):
            structured.pop(key,None)
        # Missing official-domain evidence is itself a maintenance state.  Keep the record
        # eligible for the bounded deterministic resolver instead of silently declaring the
        # company complete forever just because age/size research already succeeded.
        structured['domain_age_refresh_needed']=True
        result['facts']=facts[:12]; result['structured']=structured
        return result

    # Keep the domain itself independently of registration-age success.
    structured['domain_age_domain']=domain
    current=getattr(entity,'company_intel',{}) or {}
    current_struct=current.get('structured') if isinstance(current,dict) and isinstance(current.get('structured'),dict) else {}
    current_domain=str(current_struct.get('domain_age_domain') or '').strip().lower()
    legacy_domain=_registrable_domain(_host(_entity_url(entity))) if _first_party_candidate(_entity_url(entity)) else ''

    candidates=[]
    if current_struct.get('domain_registered_at') and ((current_domain and current_domain==domain) or (not current_domain and legacy_domain==domain)):
        candidates.append(current_struct)
    try:
        cache=CompanyResearchCache.objects.filter(domain=domain).order_by('-researched_at').first()
        cache_struct=(cache.data or {}).get('structured') if cache and isinstance(cache.data,dict) and isinstance((cache.data or {}).get('structured'),dict) else {}
        cache_domain=str(cache_struct.get('domain_age_domain') or domain).strip().lower()
        if cache_struct.get('domain_registered_at') and cache_domain==domain:
            candidates.append(cache_struct)
    except Exception:
        pass

    reused=next((row for row in candidates if row.get('domain_registered_at')),None)
    if reused:
        for key in ('domain_registered_at','domain_age_years','domain_age_label','domain_age_source','domain_age_endpoint','domain_age_checked_at'):
            if reused.get(key) not in (None,''):
                structured[key]=reused.get(key)
        structured.pop('domain_age_refresh_needed',None)
        structured.pop('domain_age_error',None)
        structured.pop('domain_age_unavailable_reason',None)
    else:
        for key in ('domain_registered_at','domain_age_years','domain_age_label'):
            structured.pop(key,None)
        structured['domain_age_checked_at']=timezone.now().isoformat()
        lookup=_rdap_lookup(domain)
        structured['domain_age_source']=str(lookup.get('source') or '')[:80]
        structured['domain_age_endpoint']=str(lookup.get('endpoint') or '')[:1000]
        if lookup.get('ok'):
            event=_rdap_registration_event(lookup.get('data') or {})
            if event:
                try:
                    from datetime import datetime, timezone as dt_timezone
                    dt=datetime.fromisoformat(event.replace('Z','+00:00')); now=datetime.now(dt_timezone.utc)
                    years=max(0,int((now-dt.astimezone(dt_timezone.utc)).days/365.2425))
                    structured['domain_registered_at']=dt.date().isoformat(); structured['domain_age_years']=years
                    structured['domain_age_label']=('<1 yr' if years<1 else (f'{years} yr' if years==1 else f'{years} yrs'))
                    structured.pop('domain_age_refresh_needed',None)
                    structured.pop('domain_age_error',None)
                    structured.pop('domain_age_unavailable_reason',None)
                except Exception as exc:
                    structured['domain_age_refresh_needed']=True
                    structured['domain_age_error']=('Invalid RDAP registration date: '+str(exc))[:500]
            else:
                # Some registries (notably .de) intentionally do not expose a domain
                # creation date. A last-changed event is not domain age, so mark this
                # authoritative absence as unavailable instead of retrying forever.
                structured.pop('domain_age_refresh_needed',None)
                structured.pop('domain_age_error',None)
                structured['domain_age_unavailable_reason']='Authoritative RDAP does not expose a registration/creation date.'
        else:
            structured['domain_age_error']=str(lookup.get('error') or 'RDAP lookup failed')[:500]
            if lookup.get('transient'):
                structured['domain_age_refresh_needed']=True
                structured.pop('domain_age_unavailable_reason',None)
            else:
                structured.pop('domain_age_refresh_needed',None)
                structured['domain_age_unavailable_reason']=structured['domain_age_error']

    if structured.get('domain_registered_at'):
        label=structured.get('domain_age_label') or ''
        facts.append({'label':'Domain Age','value':f"{label} ({domain}; registered {structured.get('domain_registered_at')})".strip(),'verification':'domain-registration'})
    result['facts']=facts[:12]; result['structured']=structured
    return result


def refresh_company_domain_registration(entity):
    """Refresh domain/RDAP metadata without invoking Local or Cloud AI.

    Returns a small status dictionary so the periodic maintenance task can remain bounded
    and observable. CompanyResearchCache is updated by normalized domain so later records
    reuse the same registration evidence instead of repeating RDAP requests.
    """
    current=getattr(entity,'company_intel',{}) or {}
    if not isinstance(current,dict): current={}
    result=dict(current)
    result.setdefault('company',str(getattr(entity,'company','') or ''))
    result.setdefault('facts',list(current.get('facts') or []))
    result.setdefault('status',current.get('status') or 'complete')
    before=json.dumps(result.get('structured') or {},sort_keys=True,default=str)
    # First reuse every piece of already stored official-domain evidence.  If a completed
    # Company Info record has none, perform one tiny bounded public search so existing rows
    # such as Phantom/GiveDirectly can acquire their official domain without another AI pass.
    if not _company_domain(entity,result):
        discovered=_discover_company_domain_from_search(entity,result)
        if discovered:
            structured=dict(result.get('structured') or {}) if isinstance(result.get('structured'),dict) else {}
            structured['company_domain']=discovered
            result['structured']=structured
    result=_domain_age_fallback(entity,result)
    structured=result.get('structured') if isinstance(result.get('structured'),dict) else {}
    domain=str(structured.get('domain_age_domain') or '').strip().lower()
    if not domain and structured.get('domain_age_refresh_needed'):
        # This maintenance attempt had no defensible official-domain result. Timestamp the
        # failed attempt here (rather than during normal company research) so fresh records
        # are eligible for one immediate maintenance pass but subsequent retries back off.
        structured['domain_age_checked_at']=timezone.now().isoformat()
        result['structured']=structured
    after=json.dumps(structured,sort_keys=True,default=str)
    changed=before!=after or result.get('facts')!=current.get('facts')
    if changed:
        entity.company_intel=result
        fields=['company_intel']
        if hasattr(entity,'updated_at'): fields.append('updated_at')
        entity.save(update_fields=fields)
    if domain:
        try:
            existing=CompanyResearchCache.objects.filter(domain=domain).first()
            cache_data=dict(existing.data or {}) if existing and isinstance(existing.data,dict) else {}
            # Prefer the richer company profile, but always merge fresh domain fields.
            if len(result.get('facts') or []) >= len(cache_data.get('facts') or []):
                cache_data=dict(result)
            else:
                cache_struct=dict(cache_data.get('structured') or {}) if isinstance(cache_data.get('structured'),dict) else {}
                cache_struct.update({k:v for k,v in structured.items() if k.startswith('domain_') and v not in (None,'')})
                cache_data['structured']=cache_struct
            CompanyResearchCache.objects.update_or_create(
                domain=domain,
                defaults={'company':str(result.get('company') or getattr(entity,'company',''))[:220],
                          'data':cache_data,'provider':getattr(existing,'provider','') if existing else '',
                          'model':getattr(existing,'model','') if existing else '',
                          'researched_at':timezone.now()},
            )
        except Exception:
            pass
    return {'changed':changed,'domain':domain,'domain_age':structured.get('domain_age_label') or '',
            'retry':bool(structured.get('domain_age_refresh_needed'))}

def _unknown_company_intel(message='Company could not be identified.'):
    return {
        'company':'','confidence':0,'facts':[],'sources':[],
        'errors':[message] if message else [],'message':message,
        'status':'complete','updated_at':timezone.now().isoformat(),
        'structured':{},
    }


def _normalise_company_result(result, raw_data=None):
    """Add compact age/size metadata while leaving unknown facts unknown."""
    result=dict(result or {}); raw_data=raw_data if isinstance(raw_data,dict) else {}
    candidate_company=_clean_research_company_name(result.get('company') or raw_data.get('company') or '')
    if result.get('company') and not candidate_company:
        unknown=_unknown_company_intel('Job board/platform is not a company identity; company information left unknown.')
        unknown.update({'provider':result.get('provider',''),'model':result.get('model',''),'source':result.get('source','')})
        return unknown
    if candidate_company:
        result['company']=candidate_company
    facts=[dict(x) for x in (result.get('facts') or []) if isinstance(x,dict)]
    previous_structured=dict(result.get('structured') or {}) if isinstance(result.get('structured'),dict) else {}
    year=''; founder=''; size=''
    for key in ('founded_year','founding_year','established_year'):
        m=re.search(r'\b(18|19|20)\d{2}\b',str(raw_data.get(key) or ''))
        if m: year=int(m.group(0)); break
    if not year:
        m=re.search(r'\b(18|19|20)\d{2}\b',str(previous_structured.get('founded_year') or ''))
        if m: year=int(m.group(0))
    founder=str(raw_data.get('founded_by') or raw_data.get('founder') or raw_data.get('founders') or previous_structured.get('founded_by') or '').strip()[:500]
    raw_size=str(raw_data.get('company_size') or raw_data.get('employee_count_or_range') or raw_data.get('size_structure') or previous_structured.get('size_range') or '')
    for f in facts:
        label=str(f.get('label') or '').lower(); val=str(f.get('value') or '')
        if not year and ('founded' in label or 'established' in label):
            m=re.search(r'\b(18|19|20)\d{2}\b',val)
            if m: year=int(m.group(0))
        if not founder and ('founded by' in label or 'founder' in label): founder=val[:500]
        if not raw_size and ('size' in label or 'employee' in label): raw_size=val
    size=_normalise_employee_size(raw_size)
    age=''
    if year:
        years=max(0,timezone.localdate().year-int(year))
        age='<1 yr' if years<1 else ('1–3 yr' if years<3 else ('3–5 yr' if years<5 else ('5–10 yr' if years<10 else '10+ yr')))
    elif previous_structured.get('age_range'):
        age=str(previous_structured.get('age_range') or '').strip()
    labels={str(f.get('label') or '').casefold() for f in facts}
    verification='verified' if result.get('sources') else 'estimate'
    if year and 'founded' not in labels: facts.append({'label':'Founded','value':str(year),'verification':verification})
    if founder and 'founded by' not in labels: facts.append({'label':'Founded by','value':founder,'verification':verification})
    for f in facts:
        f.setdefault('verification',verification)
    result['facts']=facts[:12]
    # Preserve domain-registration evidence and repair markers across normalisation.
    # Older code rebuilt the structured dict from scratch, which could silently discard
    # the domain-age fallback before Hidden Leads/contacts inherited or cached it.
    structured={
        'founded_year':year or '', 'founded_by':founder, 'age_range':age,
        'size_range':size, 'verified':verification=='verified',
    }
    for key in ('website','company_website','company_domain','domain'):
        raw_value=raw_data.get(key)
        if raw_value not in (None,''):
            structured[key]=raw_value
        elif previous_structured.get(key) not in (None,''):
            structured[key]=previous_structured.get(key)
    for key in (
        'domain_registered_at','domain_age_years','domain_age_label','domain_age_domain',
        'domain_age_refresh_needed','domain_age_checked_at','domain_age_source','domain_age_endpoint',
        'domain_age_error','domain_age_unavailable_reason',
    ):
        if previous_structured.get(key) not in (None,''):
            structured[key]=previous_structured.get(key)
    result['structured']=structured
    return result


def _save(entity, result):
    result=_normalise_company_result(result)
    if str(result.get('status') or '').casefold()=='complete':
        result=_domain_age_fallback(entity,result)
    real_company=_clean_research_company_name(result.get('company') or '')
    if not real_company and is_job_or_platform_company_name(getattr(entity,'company','')):
        entity.company=''
    elif real_company:
        entity.company=real_company[:220]
    entity.company_intel=result
    fields=['company','company_intel']
    # Contact has no updated_at field. Keep company summary/location synchronized when
    # Company Research is used for an Address Book row.
    if hasattr(entity,'company_summary'):
        summary=company_summary_from_intel(result,1200)
        if summary and not str(getattr(entity,'company_summary','') or '').strip():
            entity.company_summary=summary; fields.append('company_summary')
    if hasattr(entity,'company_country') and not str(getattr(entity,'company_country','') or '').strip():
        for fact in result.get('facts') or []:
            if isinstance(fact,dict) and str(fact.get('label') or '').strip().casefold() in {'location','hq','headquarters'}:
                value=' '.join(str(fact.get('value') or '').split()).strip()
                context=' '.join(str(x or '') for x in (value,getattr(entity,'company',''),getattr(entity,'title',''),getattr(entity,'company_summary','')))
                items=strip_non_company_location_items(value if value!='GCC' else context)
                if items:
                    entity.company_country=legacy_location_text(items)[:120]; fields.append('company_country')
                    if hasattr(entity,'company_locations'):
                        entity.company_locations=items; fields.append('company_locations')
                    break
    if hasattr(entity,'updated_at'): fields.append('updated_at')
    entity.save(update_fields=list(dict.fromkeys(fields)))
    return result


def company_intel_from_manual_filter(entity, data, provider='', model='', sources=None):
    """Build normalized Company Info from one grounded manual-filter response.

    No network/model calls are made here. Existing domain-registration metadata is retained
    so a Cloud re-check can improve age/size/company facts without discarding stronger RDAP
    evidence already collected by ScoutBox.
    """
    data=dict(data or {}) if isinstance(data,dict) else {}
    if not data:
        return getattr(entity,'company_intel',{}) or {}
    company=_clean_research_company_name(getattr(entity,'company','') or data.get('company') or '')[:220]
    facts=[]
    mapping=(
        ('What they do','what_they_do'),('Products/technology','products_technology'),
        ('Location','location'),('Founded','founded_year'),('Founded by','founded_by'),
        ('Size/structure','size_structure'),('Employee count/range','employee_count_or_range'),
    )
    for label,key in mapping:
        value=' '.join(str(data.get(key) or '').split()).strip()
        if value:
            facts.append({'label':label,'value':value[:800],'verification':'verified'})
    source_rows=[]; seen=set()
    for item in sources or []:
        if isinstance(item,dict):
            url=str(item.get('url') or '').strip()[:1000]
            title=' '.join(str(item.get('title') or url).split())[:300]
        else:
            raw=str(item or '').strip(); url=raw[:1000] if raw.startswith(('http://','https://')) else ''; title=raw[:300]
        key=(url,title.casefold())
        if (url or title) and key not in seen:
            seen.add(key); source_rows.append({'provider':'Manual filter web research','title':title or url,'url':url})
        if len(source_rows)>=12: break
    try: confidence=max(0,min(100,int(data.get('confidence') or (75 if facts else 0))))
    except Exception: confidence=75 if facts else 0
    previous=getattr(entity,'company_intel',{}) or {}
    if not source_rows and isinstance(previous,dict):
        source_rows=[dict(x) for x in (previous.get('sources') or []) if isinstance(x,dict)][:12]
    structured=dict(previous.get('structured') or {}) if isinstance(previous,dict) and isinstance(previous.get('structured'),dict) else {}
    result={
        'company':company,'confidence':confidence,'facts':facts[:12],'sources':source_rows,
        'errors':[],'status':'complete','updated_at':timezone.now().isoformat(),
        'cloud_native':True,'provider':str(provider or '')[:80],'model':str(model or '')[:200],
        'source':'manual_filter','structured':structured,
    }
    return _normalise_company_result(result,data)


def company_info_has_display_data(entity_or_intel):
    """Whether the list-view Company Info badge can show age or employee size."""
    intel=entity_or_intel if isinstance(entity_or_intel,dict) else (getattr(entity_or_intel,'company_intel',{}) or {})
    if not isinstance(intel,dict): return False
    candidate=str(intel.get('company') or '')
    if not candidate and not isinstance(entity_or_intel,dict):
        candidate=str(getattr(entity_or_intel,'company','') or '')
    fact_company=''
    for fact in intel.get('facts') or []:
        if isinstance(fact,dict) and str(fact.get('label') or '').strip().casefold()=='company':
            fact_company=str(fact.get('value') or '').strip(); break
    candidates=[candidate,fact_company]
    if any(is_job_or_platform_company_name(x) for x in candidates if x):
        return False
    if not any(str(x or '').strip() and not is_job_or_platform_company_name(x) for x in candidates):
        return False
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    if structured.get('domain_age_domain') and _job_or_platform_host(structured.get('domain_age_domain')):
        structured=dict(structured)
        for key in ('domain_registered_at','domain_age_years','domain_age_label','domain_age_domain'):
            structured.pop(key,None)
    if structured.get('founded_year') or structured.get('age_range') or structured.get('domain_age_label') or structured.get('size_range'):
        return True
    for fact in intel.get('facts') or []:
        if not isinstance(fact,dict): continue
        label=str(fact.get('label') or '').casefold(); value=str(fact.get('value') or '')
        if ('founded' in label and re.search(r'\b(?:18|19|20)\d{2}\b',value)) or (('size' in label or 'employee' in label) and re.search(r'\d',value)) or label=='domain age':
            return True
    return False


def enrich_company_intel_from_retained(entity):
    """Cheap no-network company-info repair from evidence already stored in ScoutBox.

    This is safe in Local Discovery paths and gives Company Research a better baseline.
    """
    current=ensure_company_research_baseline(entity) or {}
    if not isinstance(current,dict): current={}
    structured=dict(current.get('structured') or {}) if isinstance(current.get('structured'),dict) else {}
    text='\n'.join([_entity_text(entity),str(getattr(entity,'summary','') or ''),str(getattr(entity,'company_summary','') or ''),json.dumps(current.get('facts') or [],ensure_ascii=False,default=str)])
    changed=False
    if not structured.get('founded_year'):
        m=re.search(r'(?i)\b(?:founded|established|since)\s+(?:in\s+)?((?:18|19|20)\d{2})\b',text)
        if m:
            year=int(m.group(1)); structured['founded_year']=year
            years=max(0,timezone.localdate().year-year)
            structured['age_range']='<1 yr' if years<1 else ('1–3 yr' if years<3 else ('3–5 yr' if years<5 else ('5–10 yr' if years<10 else '10+ yr')))
            changed=True
    if not structured.get('size_range'):
        size=_normalise_employee_size(text)
        if size: structured['size_range']=size; changed=True
    if changed:
        current=dict(current); current['structured']=structured
        current['updated_at']=timezone.now().isoformat()
        _save(entity,current)
    return current




def _company_country_context(entity, previous=None):
    """Return only company-location context suitable for company research.

    Opportunity.country is a role/job country, so using it in company-registration
    searches can contaminate Company Info. Contacts and Hidden Leads do store company
    country directly. For Opportunities, reuse only explicit Company Info location/HQ.
    """
    if hasattr(entity,'company_country'):
        return clean_placeholder(getattr(entity,'company_country',''))
    if not hasattr(entity,'role_location'):
        return clean_placeholder(getattr(entity,'country',''))
    try:
        from .location import company_hq_country_from_intel
        country,_evidence,_source=company_hq_country_from_intel(previous if isinstance(previous,dict) else (getattr(entity,'company_intel',{}) or {}))
        return clean_placeholder(country)
    except Exception:
        return ''

def ensure_company_research_baseline(entity):
    """Persist a non-network baseline only for a real company identity."""
    current=getattr(entity,'company_intel',{}) or {}
    if isinstance(current,dict) and current.get('facts') and not is_job_or_platform_company_name(current.get('company')):
        return current
    company=_clean_research_company_name(getattr(entity,'company',''))
    if not company:
        company=_company_from_url(_entity_url(entity))
    if not company:
        # Do not turn a job board/ATS/source host into Company Info. Unknown is better than
        # displaying JobsDB/LinkedIn/Workday size or age for the actual employer.
        return current if isinstance(current,dict) else {}
    result=_baseline(entity,company,_company_country_context(entity,current))
    _save(entity,result)
    return result


def _parse_cloud_company(raw, company):
    import json
    text=str(raw or '').strip()
    try:
        if '```' in text:
            m=re.search(r'```(?:json)?\s*(.*?)```',text,re.S|re.I)
            if m: text=m.group(1).strip()
        a=text.find('{'); b=text.rfind('}')
        data=json.loads(text[a:b+1]) if a>=0 and b>a else {}
    except Exception:
        data={}
    facts=[]
    if isinstance(data,dict):
        mapping=[('Company','company'),('Website','website'),('What they do','what_they_do'),('Products/technology','products_technology'),('Location','location'),('Founded','founded_year'),('Founded by','founded_by'),('Size/structure','size_structure'),('Remote/international hiring','remote_hiring'),('Engagement','engagement'),('Actionability','actionability'),('Potential work paths','work_paths'),('Contact / outreach path','contact_path')]
        for label,key in mapping:
            value=data.get(key)
            if value: facts.append({'label':label,'value':str(value)[:800]})
        sources=[]
        for x in data.get('sources') or []:
            if isinstance(x,str): sources.append({'provider':'Cloud research','title':x,'url':x})
            elif isinstance(x,dict) and x.get('url'): sources.append({'provider':str(x.get('provider') or 'Cloud research')[:120],'title':str(x.get('title') or x.get('url'))[:300],'url':str(x.get('url'))[:1000]})
        try: confidence=max(25,min(98,int(data.get('confidence') or (70 if facts else 35))))
        except Exception: confidence=70 if facts else 35
        return facts,sources,confidence,data
    return [],[],25,{}


def _cache_key(entity):
    return _company_domain(entity) or ''


def _cached_company(entity, company):
    domain=_cache_key(entity)
    if not domain: return None
    row=CompanyResearchCache.objects.filter(domain=domain,researched_at__gte=timezone.now()-__import__('datetime').timedelta(days=7)).first()
    if not row or not isinstance(row.data,dict) or not row.data.get('facts'): return None
    result=dict(row.data); result['cached']=True; result['updated_at']=row.researched_at.isoformat(); result['company']=company or result.get('company','')
    return result


def _save_cache(entity,result,provider='',model=''):
    domain=_cache_key(entity)
    if not domain or not result.get('facts'): return
    CompanyResearchCache.objects.update_or_create(domain=domain,defaults={'company':str(result.get('company') or getattr(entity,'company',''))[:220],'data':result,'provider':provider[:80],'model':model[:200],'researched_at':timezone.now()})


def _dedupe_queries(values, company, domain=''):
    out=[]; seen=set(); company_key=re.sub(r'[^a-z0-9]+',' ',str(company or '').lower()).strip()
    domain_key=str(domain or '').lower().removeprefix('www.')
    for raw in values or []:
        q=re.sub(r'\s+',' ',str(raw or '')).strip().strip('"')
        if len(q)<5 or len(q)>260: continue
        low=q.lower()
        # Company research queries must stay anchored to this company/domain.
        if company_key and company_key not in re.sub(r'[^a-z0-9]+',' ',low):
            if not domain_key or domain_key not in low: continue
        key=re.sub(r'\s+',' ',low)
        if key in seen: continue
        seen.add(key); out.append(q)
    return out


def _local_company_query_suggestions(company, domain, country, fallback):
    """Optionally let the configured local model reshape company-research queries.

    This helper is used only by the Local AI Discovery/local research path. Cloud Web research
    continues to use its existing grounded research prompt unchanged.
    """
    try:
        # Company-search planning is part of company enrichment and therefore inherits
        # that visible Primary/Fallback model route. Never resolve an unrelated automatic
        # model merely because this helper is logged as query_planning.
        route=route_for_stage('company_enrichment') or {}
        if route.get('provider')!='ollama' or not route.get('model'):
            return []
        prompt=(
            'Prepare varied public-web search queries for researching one company. Return JSON only as {"queries":[...]}. '
            'Each query must include the company name or its domain. Use natural human search wording and rotate research intent: official/about, products and technology, '
            'engineering or technical team, leadership, careers or hiring, customers/projects/partnerships, independent credibility/news, and company registration where useful. '
            'Do not put government, registry, or the country name into every query. Do not invent company facts. Return 6-10 concise queries.\n\n'
            f'Company: {company}\nDomain: {domain or "unknown"}\nCountry: {country or "unknown"}\n'
            'Deterministic examples to improve rather than blindly copy:\n- '+'\n- '.join(fallback[:8])
        )
        raw=str(generate_with_route(route,prompt,stage='query_planning',subject={'type':'company_research','id':domain or company,'label':f'{company} — search query planning'}) or '').strip()
        fenced=re.search(r'```(?:json)?\s*(.*?)```',raw,re.S|re.I); payload=fenced.group(1).strip() if fenced else raw
        a=payload.find('{'); b=payload.rfind('}')
        data=json.loads(payload[a:b+1]) if a>=0 and b>a else {}
        return _dedupe_queries(data.get('queries') if isinstance(data,dict) else [],company,domain)
    except LocalAILaneBusy:
        raise
    except Exception:
        return []


def _company_query_plan(entity, company, country, max_queries=3):
    """Return a small rotating Local AI Discovery company research plan."""
    # Do not anchor research queries to LinkedIn, Greenhouse, Workday, or another career
    # portal just because the opportunity was discovered there. Use only a plausible
    # company-controlled domain; otherwise search by company name alone.
    domain=_company_domain(entity)
    anchor=f'"{company}"'
    domain_hint=f' {domain}' if domain else ''
    fallback=[
        f'{anchor}{domain_hint} official about company',
        f'{anchor}{domain_hint} products technology services',
        f'{anchor}{domain_hint} engineering technical team',
        f'{anchor}{domain_hint} leadership founders management',
        f'{anchor}{domain_hint} careers jobs hiring team',
        f'{anchor}{domain_hint} customers projects partnerships',
        f'{anchor}{domain_hint} company news funding clients',
        f'{anchor}{domain_hint} company registration {country}'.strip() if country else f'{anchor}{domain_hint} company registration',
    ]
    fallback=_dedupe_queries(fallback,company,domain)
    llm=_local_company_query_suggestions(company,domain,country,fallback)
    pool=_dedupe_queries((llm or [])+fallback,company,domain)
    if not pool: return fallback[:max_queries]
    # Rotate the starting point every six hours so repeat research does not always issue
    # the same three intents, while keeping a bounded request count.
    slot=int(timezone.now().timestamp()//21600)
    digest=hashlib.sha256(f'{company}|{domain}|{slot}'.encode('utf-8')).digest()
    offset=int.from_bytes(digest[:4],'big')%len(pool)
    rotated=pool[offset:]+pool[:offset]
    # Prefer distinct research intents: LLM output can still contain near-duplicates.
    return rotated[:max(1,int(max_queries))]


def research_company(entity):
    previous=dict(getattr(entity,'company_intel',{}) or {})
    company=_clean_research_company_name(getattr(entity,'company',''))
    if not company:
        company=_company_from_url(_entity_url(entity))
    if not company:
        result=_unknown_company_intel('Company could not be identified without using a job board/platform identity.')
        if is_job_or_platform_company_name(getattr(entity,'company','')):
            entity.company=''
            entity.company_intel=result; entity.save(update_fields=['company','company_intel']+(['updated_at'] if hasattr(entity,'updated_at') else []))
        else:
            entity.company_intel=result; entity.save(update_fields=['company_intel']+(['updated_at'] if hasattr(entity,'updated_at') else []))
        return result

    country=_company_country_context(entity,previous)
    # Persist a useful baseline only when no valid previous information exists. A manual
    # refresh must never erase a good Company Info card while network/AI work is in flight.
    result=_baseline(entity,company,country)
    if not previous.get('facts'):
        _save(entity,result)

    cached=_cached_company(entity,company)
    if cached:
        cached=_save(entity,cached)
        return cached

    # A web-capable cloud route performs the research directly in one grounded request.
    # This replaces the local fan-out of multiple search queries + page fetches when cloud
    # is actually doing the work. If it fails and a local fallback exists, continue below.
    portal_settings=PortalSettings.objects.get_or_create(pk=1)[0]
    cloud_only=str(portal_settings.discovery_mode or '').strip().lower()=='cloud_web'
    if cloud_only:
        cloud_routes=configured_cloud_web_routes('company_enrichment')
        if not cloud_routes:
            if previous.get('facts'): _save(entity,previous)
            raise RuntimeError('Cloud Web company research requires a configured Cloud Web model.')
        provider,model,_role=cloud_routes[0]
        route={'provider':provider,'model':model,'execution_mode':'cloud','fallback_provider':'','fallback_model':''}
    else:
        route=effective_route_for_stage('company_enrichment') or {}
    if is_cloud_provider(route.get('provider')):
        subject_type=_entity_subject_type(entity)
        hidden=subject_type=='hidden_lead'
        if hidden:
            prompt=(
                'Research this organization using current public web sources. There may be no job description, so judge the organization from the public evidence itself. '
                'Decide whether this is merely a technically relevant page or an organization with a realistic path to paid specialist work. '
                'Determine what the organization does, products/technology, size/structure, location, current activity, remote/international clues, '
                'founding year/founder where credible, approximate employee size, and concrete paths such as consulting/projects, specialist engineering, OSS/commercial support, technical writing, training/teaching or hiring. '
                'Identify a useful public contact/outreach path when evidenced. Include the official company website when verified. Do not invent facts. Return ONLY JSON with keys company, website, what_they_do, '
                'products_technology, location, founded_year, founded_by, size_structure, employee_count_or_range, remote_hiring, engagement, actionability, work_paths, contact_path, summary, confidence, sources. '
                'sources must be a list of objects with title and url.\n\nCompany: '+company+
                '\nKnown country: '+country+'\nSource URL: '+_entity_url(entity)+'\nCaptured evidence: '+_entity_text(entity)[:6000]
            )
        elif subject_type=='contact':
            prompt=(
                'Research this organization using current public web sources for an Address Book contact. Determine what the company does, products/technology, '
                'likely size/structure, founding year/founder where credible, base/location, and current engineering activity. Do not infer employment facts from the contact alone. '
                'Include the official company website when verified. Do not invent facts. Return ONLY JSON with keys company, website, what_they_do, products_technology, location, size_structure, founded_year, founded_by, employee_count_or_range, confidence, sources. '
                'sources must be a list of objects with title and url.\n\nCompany: '+company+
                '\nKnown country: '+country+'\nSource URL: '+_entity_url(entity)+'\nStored context: '+_entity_text(entity)[:4000]
            )
        else:
            prompt=(
                'Research this company and the supplied opportunity using current public web sources. Determine what the company does, products/technology, '
                'likely size/structure, founding year/founder where credible, base/location, whether international/remote hiring is evidenced, and contractor/full-time engagement clues. '
                'Include the official company website when verified. Do not invent facts. Return ONLY JSON with keys company, website, what_they_do, products_technology, location, size_structure, remote_hiring, '
                'engagement, founded_year, founded_by, employee_count_or_range, confidence, sources. sources must be a list of objects with title and url.\n\nCompany: '+company+
                '\nKnown country: '+country+'\nSource URL: '+_entity_url(entity)+'\nContext: '+_entity_text(entity)[:5000]
            )
        try:
            bundled=['Hidden Lead research','company information','actionability','lead summary','contact/outreach path'] if hidden else ['company information','remote/international eligibility','engagement evidence']
            with scoped_usage_context(bundle_anchor='company_enrichment',bundled_activities=bundled,jd_analysis_bypassed=bool(hidden)):
                raw,meta=web_search_with(route.get('provider'),route.get('model'),prompt,stage='company_enrichment',timeout=150)
            facts,sources,confidence,data=_parse_cloud_company(raw,company)
            if facts:
                result=_normalise_company_result({'company':company,'confidence':confidence,'facts':facts[:12],'sources':sources[:12],'errors':[],'status':'complete','updated_at':timezone.now().isoformat(),'cloud_native':True,'provider':route.get('provider',''),'model':route.get('model',''),'bundled_from':route.get('bundled_from','')},data)
                result=_save(entity,result)
                if hidden and str(data.get('summary') or '').strip():
                    entity.summary=str(data.get('summary') or '').strip()[:6000]; entity.save(update_fields=['summary','updated_at'])
                _save_cache(entity,result,route.get('provider',''),route.get('model','')); return result
        except Exception as exc:
            if cloud_only or route.get('fallback_provider')!='ollama':
                if previous.get('facts'):
                    _save(entity,previous)
                raise

    if cloud_only:
        # A Cloud Web run must never leak into Local AI Discovery public search providers.
        raise RuntimeError('Cloud Web company research failed; Local AI Discovery search fallback is disabled.')

    evidence=[]; errors=[]; seen=set()
    def add_evidence(provider,title,url,snippet):
        url=str(url or '').strip()
        if not url or url in seen: return
        seen.add(url)
        evidence.append({'provider':str(provider or '')[:120],'title':str(title or '')[:300],'url':url[:1000],'snippet':re.sub(r'\s+',' ',str(snippet or '')).strip()[:1800]})

    # Existing first-party page content is valid evidence and gives research something to
    # work with even when every public search provider is temporarily unavailable.
    source_url=_entity_url(entity)
    source_text=_entity_text(entity)
    if source_url and _first_party_candidate(source_url):
        add_evidence('Existing source',_entity_title(entity),source_url,source_text[:1800])
        root=_root_url(source_url)
        if root:
            try:
                page=fetch_target(root,'','',timeout=12)
                if page.get('ok'):
                    add_evidence('Company website',page.get('title') or company,root,page.get('text') or '')
            except Exception as exc:
                errors.append(f'Company website: {exc}')

    queries=_company_query_plan(entity,company,country,max_queries=3)
    for provider in _providers():
        for q in queries:
            rows,err=search_source(provider,q,limit=4,usage_category='company_research')
            if err:
                errors.append(f'{provider.name}: {err}')
                continue
            for row in rows[:4]:
                add_evidence(provider.name,row.get('title',''),row.get('url',''),row.get('snippet',''))
            if len(evidence)>=18: break
        if len(evidence)>=18: break

    # Fetch a small number of likely first-party result pages. Search snippets can be thin;
    # these page excerpts materially improve products/technology and company-description facts.
    fetched_hosts=set()
    for item in list(evidence):
        if len(fetched_hosts)>=2: break
        url=item.get('url',''); host=_host(url)
        if not _first_party_candidate(url) or not host or host in fetched_hosts: continue
        fetched_hosts.add(host)
        try:
            page=fetch_target(_root_url(url) or url,item.get('title',''),item.get('snippet',''),timeout=12)
            if page.get('ok'):
                add_evidence('Company website',page.get('title') or item.get('title',''),page.get('target_url') or url,page.get('text') or '')
        except Exception as exc:
            errors.append(f'{host}: {exc}')

    facts=[]
    confidence=min(90,30+len(evidence)*3)
    if evidence:
        prompt=(
            "Summarize public company information from the supplied evidence only. "
            "Do not infer facts not supported by the evidence. Return 4-8 concise lines, each exactly as LABEL: value. "
            "Useful labels include Company, What they do, Products/technology, Location, Founded, Founded by, Size/structure, Public registry, Relevant engineering activity. "
            "If a fact is not supported, omit it.\n\n"+
            '\n'.join(f"[{x['provider']}] {x['title']} | {x['snippet']} | {x['url']}" for x in evidence[:16])
        )
        try:
            out=generate(prompt,stage='company_enrichment',timeout=90,subject={'type':_entity_subject_type(entity),'id':entity.pk,'label':f'{company} — company research'})
            for line in (out or '').splitlines():
                line=re.sub(r'^[-*•\s]+','',line).strip().replace('**','')
                if ':' in line:
                    k,v=line.split(':',1); k=k.strip(); v=v.strip()
                    if k and v: facts.append({'label':k[:80],'value':v[:800]})
        except LocalAILaneBusy:
            raise
        except Exception as exc:
            errors.append(f'AI summary: {exc}')

    if not facts:
        facts=[{'label':'Company','value':company}]
        if country: facts.append({'label':'Location','value':country})
        # Show concise sourced excerpts rather than leaving the card blank when AI is down.
        for x in evidence[:4]:
            snippet=x.get('snippet','')
            if snippet:
                label=(x.get('title') or x.get('provider') or 'Public source')[:80]
                if not any(f['label']==label and f['value']==snippet[:600] for f in facts):
                    facts.append({'label':label,'value':snippet[:600]})

    result={
        'company':company,'confidence':confidence,'facts':facts[:10],'sources':evidence[:12],
        'errors':errors[:8],'status':'complete','updated_at':timezone.now().isoformat(),
    }
    # A failed/weak refresh must not replace stronger previously verified information.
    if previous.get('facts') and errors and len(evidence)==0:
        preserved=dict(previous)
        preserved['last_refresh_error']='; '.join(errors[:3])[:1200]
        preserved['last_refresh_attempt_at']=timezone.now().isoformat()
        preserved=_save(entity,preserved)
        return preserved
    result=_save(entity,result)
    _save_cache(entity,result)
    return result
