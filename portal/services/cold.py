import hashlib
import json
import os
import re
import time
import urllib.parse
from difflib import SequenceMatcher
from django.utils import timezone
from django.db.models import Q
from portal.models import CompanyLead, Profile, SearchSource, PortalSettings, UsageMetric, Opportunity, Application
from portal.ui import COUNTRIES
from .search import search_source, ACTIVE_PROVIDER_NAMES, provider_selection_details, provider_query_allowance, provider_market_compatible, unwrap_search_result_url, is_search_engine_url
from .queryplanner import build_search_profile
from .ai import generate
from .cloud_budget import CloudLimitReached
from .dedup import active_duplicate_lead, active_opportunity_for_company
from .pagefetch import fetch_target, primarily_english
from .blacklist import is_blacklisted_url
from .opportunity_urls import is_disallowed_adult_url
from .content_quality import adult_content_reason
from .campaign_links import copy_lead_campaigns_to_opportunity
from .mailbox import promote_record_contact_to_addressbook, assignable_contact_email, clean_contact_email, contact_company_from_email
from .platforms import is_job_platform_host, is_platform_company_name, is_plausible_company_name
from .company_research import company_domain_for_entity, company_summary_from_intel, company_info_has_display_data, stored_company_context
from .selectivity import current as selectivity_current, lead_policy, instruction as selectivity_instruction
from .discovery_markets import market_plan, market_workload_schedule, market_query, market_search_meta, multilingual_assignments, MARKET_BY_CODE

ACTIVITY_PHRASES=[
    'working on','building','developing','maintaining','supporting','porting','migrating','modernizing','reverse engineering',
    'firmware','device driver','driver','bootloader','emulator','emulation','legacy product','legacy system','protocol','hardware bring-up',
    'compatibility','old hardware','embedded product','board support','toolchain','low-level','binary format','retro computing','virtualization',
]
NOISE=('job opening','apply now','careers','vacancy','we are hiring','job description')

def _hidden_page_is_job_like(url, title='', text=''):
    """Detect an actual vacancy page without rejecting company pages whose nav says Careers."""
    try:
        path=(urllib.parse.urlparse(str(url or '')).path or '').casefold()
    except Exception:
        path=''
    title_low=' '.join(str(title or '').casefold().split())
    body=' '.join(str(text or '').casefold().split())[:18000]
    if re.search(r'/(?:jobs?|careers?|vacanc(?:y|ies)|positions?|openings?)(?:/|$)',path):
        return True
    if any(x in title_low for x in ('job opening','vacancy','we are hiring','careers at ','apply now')):
        return True
    strong=sum(1 for marker in ('apply now','job description','responsibilities','qualifications','requirements','employment type','salary range') if marker in body)
    return strong>=3 or ('we are hiring' in body and ('apply' in body or 'position' in body))
GENERAL_PLATFORM_HOSTS=(
    'google.com','bing.com','duckduckgo.com','search.brave.com','yahoo.com',
    'linkedin.com','indeed.com','glassdoor.com','facebook.com','instagram.com',
    'twitter.com','x.com','reddit.com','youtube.com','tiktok.com','monster.com',
    'ziprecruiter.com','simplyhired.com','wellfound.com','seek.com','jobsdb.com','findjob24h.com',
    'github.com','bitbucket.org','gitlab.com','medium.com','dev.to','substack.com',
    'xda-developers.com','hackaday.com','tomshardware.com','arstechnica.com','theverge.com','slashdot.org','lobste.rs',
    'stackoverflow.com','stackexchange.com','sourceforge.net','npmjs.com','pypi.org',
    'wordpress.com','blogspot.com','hashnode.com','news.ycombinator.com',
    'freelancer.com','upwork.com','fiverr.com','peopleperhour.com','guru.com','arm.com','kernel.org',
)

GENERAL_PLATFORM_BRANDS={'linkedin','indeed','glassdoor','facebook','instagram','twitter','reddit','youtube','tiktok','monster','ziprecruiter','simplyhired','wellfound','seek','jobsdb','findjob24h','freelancer','upwork','fiverr','peopleperhour','guru'}
GENERAL_PLATFORM_COMPANIES={'xda developers','hackaday','tomshardware','ars technica','the verge','slashdot','lobsters','google','bing','duckduckgo','yahoo','linkedin','indeed','glassdoor','facebook','instagram','twitter','reddit','youtube','tiktok','monster','ziprecruiter','simplyhired','wellfound','seek','jobsdb','findjob24h','github','bitbucket','gitlab','medium','devto','substack','stackoverflow','stackexchange','sourceforge','npmjs','pypi','wordpress','blogspot','hashnode','ycombinator','freelancer','upwork','fiverr','peopleperhour','guru'}

PUBLIC_SUFFIX_2={'co.uk','org.uk','ac.uk','com.au','net.au','org.au','co.nz','com.sg','com.my','co.jp','co.kr','ac.kr','co.in','com.br','com.cn','com.tw','edu.sg'}
DOC_HOSTS={'man7.org','manpages.ubuntu.com','linux.die.net','readthedocs.io','readthedocs.org','docs.python.org','developer.mozilla.org','kernel.org','arm.com'}
DOC_TITLE_MARKERS=('man page','manual page','api reference','documentation','reference guide','command reference','linux manual','developer documentation','technical documentation','user guide','installation guide','knowledge base')

def source_domain(url):
    try:
        host=urllib.parse.urlparse(str(url or '')).netloc.lower().split('@')[-1].split(':')[0].removeprefix('www.')
    except Exception:
        return ''
    return host


def registrable_domain(url_or_host):
    raw=str(url_or_host or '')
    host=source_domain(raw) if '://' in raw else raw.lower().split(':',1)[0].removeprefix('www.')
    labels=[x for x in host.split('.') if x]
    if len(labels)<2: return host
    tail='.'.join(labels[-2:])
    if tail in PUBLIC_SUFFIX_2 and len(labels)>=3: return '.'.join(labels[-3:])
    return tail

def recycled_lead_match(company='', url=''):
    """Return a matching Hidden Lead while it remains in the Recycle Bin."""
    deleted=CompanyLead.objects.filter(user_deleted=True)
    label=re.sub(r'\s+',' ',str(company or '')).strip()
    if label:
        exact=deleted.filter(company__iexact=label).first()
        if exact: return exact
    domain=registrable_domain(url)
    if domain:
        by_domain=deleted.filter(Q(target_url__icontains=domain)|Q(source_url__icontains=domain)|Q(search_url__icontains=domain)).first()
        if by_domain: return by_domain
    return None

def is_documentation_like(url,title='',text=''):
    host=source_domain(url); path=(urllib.parse.urlparse(str(url or '')).path or '').lower()
    if not host: return False
    if host.startswith(('wiki.','docs.','documentation.','man.','manual.','help.','kb.','support-docs.')): return True
    if any(host==d or host.endswith('.'+d) for d in DOC_HOSTS): return True
    if any(seg in path for seg in ('/wiki/','/docs/','/documentation/','/manual/','/man/','/man-pages/','/reference/','/api-reference/','/api/','/guide/','/guides/','/help/','/kb/','/forum/','/forums/','/community/','/support/','/thread/','/threads/','/questions/')): return True
    heading=(' '+str(title or '').lower()+' ')
    if any(marker in heading for marker in DOC_TITLE_MARKERS): return True
    sample=(' '+str(text or '')[:2500].lower()+' ')
    if (' synopsis ' in sample and ' options ' in sample and (' man page ' in sample or ' command ' in sample)): return True
    return False

_BRAND_SUFFIX_WORDS=(
    'intelligence','technologies','technology','microelectronics','semiconductors','semiconductor',
    'electronics','engineering','solutions','systems','software','hardware','computing','networks',
    'security','robotics','automation','innovations','conversions','devices','digital','research','embedded','labs','global',
    'incorporated','corporation','company','limited','inc','llc','ltd','corp','gmbh','plc',
)

def _humanize_domain_brand(base):
    raw=re.sub(r'[-_]+',' ',str(base or '')).strip()
    if not raw: return ''
    if ' ' in raw: return ' '.join(x.capitalize() if x.islower() else x for x in raw.split())
    # Preserve obvious CamelCase before applying a conservative suffix split to all-lowercase domains.
    camel=re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',raw)
    if camel!=raw: return camel.strip()
    low=raw.lower()
    # Domain-derived company tokens often preserve connector words without spaces
    # (for example oadbyplastics). Split only when both sides are substantial so
    # normal short brand names and acronyms are left alone.
    connected=re.sub(r'(?<=[a-z]{3})(by|and|for|with)(?=[a-z]{3})',r' \1 ',low)
    if connected!=low:
        return ' '.join(part.capitalize() for part in connected.split())
    # Keep this deliberately narrow.  The user-facing cleanup is a fallback for
    # domain-shaped labels, not a general word-segmentation engine: broad rules
    # such as ``micro*`` would incorrectly rewrite real brands such as Microchip.
    # ``robopenguins`` is a known domain-style case and safely splits at ``robo``.
    if low.startswith('robo') and len(low) >= 9:
        tail=low[4:]
        if tail.isalpha():
            return f'Robo {tail.capitalize()}'
    for suffix in sorted(_BRAND_SUFFIX_WORDS,key=len,reverse=True):
        if low.endswith(suffix) and len(low)>len(suffix)+2:
            prefix=low[:-len(suffix)].strip()
            if prefix:
                return f'{prefix.capitalize()} {suffix.capitalize()}'
    return raw.capitalize()


def display_company_name(name, url=''):
    """Return a conservative human-readable company label for list views.

    Legacy Hidden Leads sometimes persisted the registrable-domain token verbatim
    (for example ``mordorintelligence``).  Keep real brand names untouched, but
    split obvious domain-derived suffixes so the list reads naturally.
    """
    clean=re.sub(r'\s+',' ',str(name or '')).strip()
    domain=registrable_domain(url)
    base=(domain.split('.')[0] if domain else '')
    norm=lambda value: re.sub(r'[^a-z0-9]+','',str(value or '').lower())
    if clean and base and norm(clean)==norm(base):
        return (_humanize_domain_brand(base) or clean)[:220]
    if clean and ' ' not in clean and len(clean)>=7:
        human=_humanize_domain_brand(clean)
        if human and human.lower()!=clean.lower() and ' ' in human:
            return human[:220]
    return clean[:220]


_THIRD_PARTY_EMPLOYER_HOSTS={
    'linkedin.com','indeed.com','glassdoor.com','github.com','gitlab.com','bitbucket.org','wellfound.com',
    'ziprecruiter.com','simplyhired.com','monster.com','seek.com','jobsdb.com','findjob24h.com','reddit.com',
}
_THIRD_PARTY_EMAIL_RE=re.compile(r'(?i)(?<![A-Z0-9._%+\-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![A-Z0-9._%+\-])')


def _third_party_host(url):
    domain=registrable_domain(url)
    return bool(is_job_platform_host(domain) or domain.endswith('.edu') or '.ac.' in domain or domain.endswith('.ac.kr'))


def _company_from_third_party_job_evidence(url, text=''):
    """Recover the actual employer from explicit third-party job-page evidence.

    Listing hosts are never employers.  Prefer structured/labelled evidence, then
    narrowly-scoped natural-language constructions used in job summaries.
    """
    if not _third_party_host(url):
        return ''
    raw=str(text or '')
    if not raw:
        return ''

    def accept(value):
        company=' '.join(str(value or '').split()).strip(' -–—|:;,')[:220]
        return company if is_plausible_company_name(company) else ''

    # JSON-LD / structured JobPosting is strongest.
    structured_patterns=(
        r'(?is)["\']hiringOrganization["\']\s*:\s*\{.{0,900}?["\']name["\']\s*:\s*["\']([^"\']{2,120})["\']',
        r'(?is)["\']hiringOrganization["\']\s*:\s*["\']([^"\']{2,120})["\']',
    )
    for pattern in structured_patterns:
        m=re.search(pattern,raw)
        if m:
            company=accept(m.group(1))
            if company: return company

    # Explicit board labels.
    label_patterns=(
        r'(?im)^\s*(?:company|employer|organisation|organization|hiring company)\s*[:\-]\s*([^\r\n]{2,120})\s*$',
        r'(?im)^\s*(?:company|employer|organisation|organization|hiring company)\s*$\s*^\s*([^\r\n]{2,120})\s*$',
    )
    for pattern in label_patterns:
        m=re.search(pattern,raw)
        if m:
            company=accept(m.group(1))
            if company: return company

    # Job-board summaries commonly start "OpenAI seeks..." / "Coinbase is hiring...".
    prose_patterns=(
        r'(?im)^\s*([A-Z][A-Za-z0-9&+.’\'()\- ]{1,80}?)\s+(?:seeks|is seeking|is hiring|is looking for|looks for|hiring)\b',
        r'(?im)^\s*(?:job|role|position)\s+at\s+([A-Z][^\r\n|]{1,100})\s*$',
        # Summary/title prose such as "Lead Senior Software Engineer, Java at NinjaOne. Build..."
        r'(?i)\b(?:engineer|developer|writer|manager|specialist|researcher|architect|consultant|analyst|designer|administrator|scientist)[^.\n]{0,110}?\s+at\s+([A-Z][A-Za-z0-9&+.’\'()\- ]{1,70}?)(?=[.,;]|\s+(?:build|develop|design|work|join|help|create)\b)',
    )
    for pattern in prose_patterns:
        m=re.search(pattern,raw)
        if m:
            company=accept(m.group(1))
            if company: return company

    # A company mailbox can corroborate a company name mentioned elsewhere in the page.
    source_reg=registrable_domain(url)
    for found in _THIRD_PARTY_EMAIL_RE.findall(raw):
        email=clean_contact_email(found)
        if not assignable_contact_email(email,raw):
            continue
        email_domain=registrable_domain(email.split('@',1)[1] if '@' in email else '')
        if not email_domain or email_domain==source_reg:
            continue
        company=contact_company_from_email(email)
        if not is_plausible_company_name(company):
            continue
        slug=re.sub(r'[^a-z0-9]+','',company.casefold())
        if len(slug)<5:
            continue
        scrubbed=re.sub(re.escape(email),' ',raw,flags=re.I)
        scrubbed=re.sub(re.escape(email_domain),' ',scrubbed,flags=re.I)
        normalized=re.sub(r'[^a-z0-9]+','',scrubbed.casefold())
        if slug in normalized:
            return company[:220]
    return ''


def _company_from_linkedin_job(text):
    """Recover the hiring company from retained LinkedIn job text.

    LinkedIn is the host, not the employer. Public job pages consistently expose the
    employer in either the ``role at`` line, the ``See who ... has hired`` line, or the
    first title/company/location header block. Return blank rather than invent LinkedIn.
    """
    raw=str(text or '')
    if not raw:
        return ''
    patterns=(
        r'(?im)^\s*role at\s*$\s*^\s*([^\r\n]{2,220})\s*$',
        r'(?im)^\s*See who\s+(.+?)\s+has hired for this role\s*$',
        r'(?is)\brole at\s*[\r\n]+\s*([^\r\n]{2,220})',
    )
    for pattern in patterns:
        m=re.search(pattern,raw)
        if not m:
            continue
        company=' '.join(m.group(1).split()).strip(' -–—|:')[:220]
        if is_plausible_company_name(company):
            return company
    lines=[' '.join(line.split()).strip() for line in raw.splitlines()]
    lines=[line for line in lines if line]
    if len(lines)>=3:
        candidate=lines[1].strip(' -–—|:')[:220]
        if is_plausible_company_name(candidate):
            return candidate
    return ''


def company_from_page(url,title='',text=''):
    domain=registrable_domain(url)
    if not domain: return ''
    if domain=='linkedin.com':
        linked=_company_from_linkedin_job(text) if '/jobs/' in str(url or '').lower() else ''
        if linked: return linked
        # LinkedIn is always the host, never a fallback employer label.
        return _company_from_third_party_job_evidence(url,text)
    hosted=_company_from_third_party_job_evidence(url,text)
    if hosted:
        return hosted
    if is_job_platform_host(domain):
        # A known listing/community/ATS host is never the employer merely because no better
        # company could be recovered from this page.
        return ''
    title_clean=re.sub(r'\s+',' ',str(title or '')).strip()
    base=re.sub(r'[^a-z0-9]+','',domain.split('.')[0].lower())
    generic_title={'home','home page','homepage','welcome','official site','about','about us'}
    # Prefer a concise brand-like title segment. "Home page | Mordor Intelligence" should
    # yield "Mordor Intelligence", not the concatenated registrable-domain token.
    parts=[x.strip() for x in re.split(r'\s*[|–—:]\s*|\s+-\s+',title_clean) if x.strip()]
    for part in parts:
        low=part.lower().strip()
        if low in generic_title or any(x in low for x in ('documentation','docs','manual','reference','wiki','blog','jobs','careers')):
            continue
        if not (2 <= len(part) <= 70): continue
        token=re.sub(r'[^a-z0-9]+','',low)
        if base and token and (base==token or base in token or token in base):
            return re.sub(r'(?i)^(?:home(?: page)?|welcome)\s*[-–—|:]\s*','',part).strip()[:220]
    academic_known={'unc.edu':'University of North Carolina at Chapel Hill','mit.edu':'Massachusetts Institute of Technology','stanford.edu':'Stanford University','berkeley.edu':'University of California, Berkeley','cmu.edu':'Carnegie Mellon University'}
    if domain in academic_known: return academic_known[domain]
    if domain.endswith('.edu'):
        for part in parts:
            low=part.lower()
            if 3 <= len(part) <= 90 and low not in generic_title and not any(x in low for x in ('documentation','docs','manual','reference','wiki','jobs','careers')):
                return part[:220]
    for part in parts:
        low=part.lower()
        if 3 <= len(part) <= 80 and not any(x in low for x in ('documentation','docs','manual','reference','wiki','jobs','careers')) and any(x in low for x in ('university','institute','laboratory','lab','college','school','foundation','project')):
            return part[:220]
    raw_base=domain.split('.')[0]
    return (_humanize_domain_brand(raw_base) or domain)[:220]


COUNTRY_TLDS={'.sg':'Singapore','.au':'Australia','.uk':'United Kingdom','.de':'Germany','.fr':'France','.jp':'Japan','.ca':'Canada','.nz':'New Zealand','.ch':'Switzerland','.nl':'Netherlands','.se':'Sweden','.no':'Norway','.fi':'Finland','.in':'India','.br':'Brazil'}
COUNTRY_NAMES=tuple(COUNTRIES)
_COUNTRY_CODE_ALIASES={
    'US':'United States','USA':'United States','GB':'United Kingdom','GBR':'United Kingdom','UK':'United Kingdom',
    'SG':'Singapore','SGP':'Singapore','AU':'Australia','AUS':'Australia','CA':'Canada','CAN':'Canada','DE':'Germany','DEU':'Germany',
    'FR':'France','FRA':'France','JP':'Japan','JPN':'Japan','NZ':'New Zealand','NZL':'New Zealand','CH':'Switzerland','CHE':'Switzerland',
    'NL':'Netherlands','NLD':'Netherlands','SE':'Sweden','SWE':'Sweden','NO':'Norway','NOR':'Norway','FI':'Finland','FIN':'Finland',
    'IN':'India','IND':'India','BR':'Brazil','BRA':'Brazil','MY':'Malaysia','MYS':'Malaysia','ID':'Indonesia','IDN':'Indonesia',
    'VN':'Vietnam','VNM':'Vietnam','TH':'Thailand','THA':'Thailand','PH':'Philippines','PHL':'Philippines','CN':'China','CHN':'China',
    'TW':'Taiwan','TWN':'Taiwan','HK':'Hong Kong','HKG':'Hong Kong','KR':'South Korea','KOR':'South Korea',
}
_US_STATE_CODES={
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT',
    'NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC',
}
_US_STATE_NAMES={
    'alabama','alaska','arizona','arkansas','california','colorado','connecticut','delaware','florida','georgia','hawaii','idaho','illinois',
    'indiana','iowa','kansas','kentucky','louisiana','maine','maryland','massachusetts','michigan','minnesota','mississippi','missouri','montana',
    'nebraska','nevada','new hampshire','new jersey','new mexico','new york','north carolina','north dakota','ohio','oklahoma','oregon',
    'pennsylvania','rhode island','south carolina','south dakota','tennessee','texas','utah','vermont','virginia','washington','west virginia',
    'wisconsin','wyoming','district of columbia',
}

def _country_from_location_hint(value):
    """Resolve a country from structured/explicit location evidence only.

    This intentionally gives JSON-LD JobPosting address fields and a US city/state pair
    priority over arbitrary country words elsewhere on a page. Job boards frequently
    contain navigation, office lists or candidate-profile text mentioning unrelated
    countries; using the first country token caused San Francisco roles to be stored as
    Singapore when "Singapore" appeared earlier in the document.
    """
    raw=' '.join(str(value or '').split()).strip()
    if not raw:
        return ''
    # Full retained JSON-LD blobs must not be saved/displayed as the country.
    # Extract a single explicit country only; a long applicant-country list means
    # many eligible countries, not one reliable role/company country.
    if raw[0] in '[{':
        try:
            parsed=json.loads(raw)
        except Exception:
            parsed=None
        if parsed is not None:
            found=[]
            def add(candidate):
                token=' '.join(str(candidate or '').split()).strip(' \"\'.:,;{}[]()')
                if not token:
                    return
                token=_COUNTRY_CODE_ALIASES.get(token.upper(),token)
                for name in COUNTRY_NAMES:
                    if token.casefold()==name.casefold() and name not in found:
                        found.append(name)
                        return
            def walk(obj):
                if isinstance(obj,dict):
                    typ=str(obj.get('@type') or obj.get('type') or '').casefold()
                    if 'country' in typ:
                        add(obj.get('name') or obj.get('alternateName'))
                    for key in ('addressCountry','country','countryCode'):
                        if key in obj:
                            value=obj.get(key)
                            if isinstance(value,(dict,list)):
                                walk(value)
                            else:
                                add(value)
                    for value in obj.values():
                        if isinstance(value,(dict,list)):
                            walk(value)
                elif isinstance(obj,list):
                    for value in obj:
                        walk(value)
                elif isinstance(obj,str):
                    add(obj)
            walk(parsed)
            return found[0] if len(found)==1 else ''
    # JSON-LD and similar retained structured location strings.
    m=re.search(r'(?i)["\']?(?:addressCountry|country)["\']?\s*[:=]\s*["\']?([A-Za-z .-]{2,45})',raw)
    if m:
        token=m.group(1).strip(' \"\'.,;:}])')
        code=_COUNTRY_CODE_ALIASES.get(token.upper())
        if code:
            return code
        for name in COUNTRY_NAMES:
            if token.casefold()==name.casefold():
                return name
    # A city followed by a two-letter US state code is strong job-location evidence.
    # Keep this case-sensitive so ordinary words such as "in" do not look like IN.
    for m in re.finditer(r'\b[A-Z][A-Za-z .\-]{1,55},\s*([A-Z]{2})(?:\s+\d{5}(?:-\d{4})?)?(?=\b|[,;])',raw):
        if m.group(1) in _US_STATE_CODES:
            return 'United States'
    # JSON-LD often carries addressRegion without a locality immediately before it.
    m=re.search(r'["\']?addressRegion["\']?\s*[:=]\s*["\']?([A-Z]{2})["\']?',raw)
    if m and m.group(1) in _US_STATE_CODES:
        return 'United States'
    # City, full-state-name is also sufficiently specific.
    m=re.search(r'\b[A-Z][A-Za-z .\-]{1,55},\s*([A-Za-z ]{4,25})(?=\b|[,;])',raw)
    if m and m.group(1).strip().casefold() in _US_STATE_NAMES:
        return 'United States'
    # Finally accept an explicit country when this value itself is a location field.
    aliases={'usa':'United States','u.s.':'United States','u.s.a.':'United States','united states of america':'United States','us':'United States',
             'uk':'United Kingdom','u.k.':'United Kingdom','great britain':'United Kingdom','singapore':'Singapore','australia':'Australia'}
    low=' '+raw.casefold()+' '
    for alias,name in aliases.items():
        if re.search(r'(?<![a-z])'+re.escape(alias)+r'(?![a-z])',low):
            return name
    for name in COUNTRY_NAMES:
        if re.search(r'(?i)(?<![A-Za-z])'+re.escape(name)+r'(?![A-Za-z])',raw):
            return name
    return ''

def infer_country(url,text='',location_hint='',strict=False):
    """Infer the role/company country, preferring explicit location evidence.

    ``location_hint`` is intended for JobPosting JSON-LD or a known location field.
    For ordinary page text, high-confidence city/state and labelled location snippets
    are considered before the legacy first-country fallback.
    """
    hinted=_country_from_location_hint(location_hint)
    if hinted:
        return hinted
    raw=' '.join(str(text or '').split())[:18000]
    # High-confidence US city/state evidence must beat unrelated office/footer country
    # names elsewhere in the page (for example Singapore on a San Francisco vacancy).
    high=_country_from_location_hint(re.sub(r'(?i)(addressCountry|country)\s*[:=]','',raw)) if raw else ''
    if high=='United States':
        return high
    # Prefer short labelled location fragments to arbitrary country mentions.
    for m in re.finditer(r'(?i)\b(?:job\s+location|work\s+location|location\s+requirements?|location|based\s+in|hiring\s+in)\s*[:\-]\s*([^|•\n]{2,120})',raw):
        explicit=_country_from_location_hint(m.group(1))
        if explicit:
            return explicit
    if strict:
        return ''
    blob=' '+raw.lower()+' '
    aliases={'usa':'United States','u.s.':'United States','united states of america':'United States','uk':'United Kingdom','u.k.':'United Kingdom','singapore':'Singapore','australia':'Australia'}
    for alias,name in aliases.items():
        if re.search(r'(?<![a-z])'+re.escape(alias)+r'(?![a-z])',blob): return name
    for name in COUNTRY_NAMES:
        if (' '+name.lower()+' ') in blob: return name
    host=source_domain(url)
    if host.endswith('.edu'):
        return 'United States'
    for tld,name in COUNTRY_TLDS.items():
        if host.endswith(tld): return name
    return ''

def _summary_topics(text):
    blob=(' '+re.sub(r'\s+',' ',str(text or '')).lower()+' ')
    topics=[]
    aliases=[
        ('reverse engineering',('reverse engineering','reverse-engineering')),
        ('binary analysis',('binary analysis','binary-analysis')),
        ('firmware',('firmware',)),('embedded systems',('embedded system','embedded linux','embedded software')),
        ('device drivers',('device driver','kernel driver')),('emulation',('emulation','emulator')),
        ('virtualization',('virtualization','virtualisation','qemu')),('legacy systems',('legacy system','legacy software','retro computing')),
        ('protocols',('protocol',)),('hardware bring-up',('hardware bring-up','board bring-up')),
        ('GPU computing',('gpu','cuda','opencl','vulkan compute')),('AI systems',('artificial intelligence','machine learning','neural network','inference engine','llm')),
    ]
    for label,needles in aliases:
        if any(n in blob for n in needles): topics.append(label)
    return topics[:4]


_GENERIC_HIDDEN_LEAD_CONTEXTS=(
    'engineering and product-development services',
    'embedded software or firmware products',
    'software platforms and developer tools',
    'hardware and electronics systems',
    'industrial or IoT systems',
    'emulation and virtualization technology',
    'legacy modernization, migration or porting',
)
_GENERIC_HIDDEN_LEAD_TOPICS=(
    'reverse engineering','binary analysis','firmware','embedded systems','device drivers',
    'emulation','virtualization','legacy systems','protocols','hardware bring-up','GPU computing','AI systems',
)

# structured_visible_text() deliberately adds section markers so downstream analyzers can
# reason about page scope. Those markers are evidence metadata, never user-facing prose.
_HIDDEN_LEAD_EVIDENCE_SECTION_RE=re.compile(
    r'\[(PAGE_TITLE|CURRENT_JOB_HEADER|JOB_DESCRIPTION|RESPONSIBILITIES|QUALIFICATIONS|BENEFITS|COMPENSATION|APPLICATION|COMPANY_PROFILE|RELATED_JOBS|FOOTER|NAVIGATION|SOURCE_URL|TITLE|TEXT)\]',
    re.I,
)
_HIDDEN_LEAD_EVIDENCE_PREFIX_RE=re.compile(r'^\s*\[[A-Z][A-Z0-9_ -]{2,40}\]\s*')
_HIDDEN_LEAD_SUMMARY_SKIP_SECTIONS={
    'CURRENT_JOB_HEADER','RESPONSIBILITIES','QUALIFICATIONS','BENEFITS','COMPENSATION',
    'APPLICATION','RELATED_JOBS','FOOTER','NAVIGATION','SOURCE_URL','TITLE',
}


def hidden_lead_summary_has_evidence_markers(summary):
    """True when structured page-evidence labels leaked into summary prose."""
    text=str(summary or '')
    return bool(_HIDDEN_LEAD_EVIDENCE_SECTION_RE.search(text) or _HIDDEN_LEAD_EVIDENCE_PREFIX_RE.search(text))


def strip_hidden_lead_evidence_markers(value):
    """Remove extraction/provenance labels while preserving the useful prose after them."""
    text=str(value or '')
    if not text:
        return ''
    # Known labels can occur between otherwise useful sentences. Remove every one, not
    # only the leading token. Then remove any remaining generic leading [SECTION] label.
    text=_HIDDEN_LEAD_EVIDENCE_SECTION_RE.sub(' ',text)
    text=_HIDDEN_LEAD_EVIDENCE_PREFIX_RE.sub('',text)
    text=re.sub(r'\s+',' ',text).strip(' \t\r\n-–—|·:;')
    return text


def _company_summary_evidence_segments(text):
    """Yield summary-eligible evidence segments without exposing structural labels."""
    raw=str(text or '').strip()
    if not raw:
        return []
    matches=list(_HIDDEN_LEAD_EVIDENCE_SECTION_RE.finditer(raw))
    if not matches:
        return [('',raw)]
    out=[]
    prefix=raw[:matches[0].start()].strip()
    if prefix:
        out.append(('',prefix))
    for index,match in enumerate(matches):
        section=match.group(1).upper()
        end=matches[index+1].start() if index+1 < len(matches) else len(raw)
        body=raw[match.end():end].strip()
        if body and section not in _HIDDEN_LEAD_SUMMARY_SKIP_SECTIONS:
            out.append((section,body))
    return out


def hidden_lead_summary_is_generic(summary):
    """True when a lead description is only a reusable taxonomy/template sentence."""
    text=re.sub(r'\s+',' ',str(summary or '')).strip()
    if not text:
        return True
    low=text.casefold()
    first=re.split(r'(?<=[.!?])\s+',text,1)[0].strip().casefold()
    if first in {
        'summary pending.',
        'appears relevant to low-level product engineering, although the specific products or services need more verification.',
        'no clear product or service context could be verified from the captured public material. review the source before using this as an outreach lead.',
    }:
        return True
    for a in _GENERIC_HIDDEN_LEAD_CONTEXTS:
        if first == f'specializes in {a.casefold()}.':
            return True
        for b in _GENERIC_HIDDEN_LEAD_CONTEXTS:
            if a != b and first == f'specializes in {a.casefold()} and {b.casefold()}.':
                return True
    if first.startswith('focuses on ') and first.endswith('.'):
        payload=first[len('focuses on '):-1]
        parts=[x.strip() for x in re.split(r',|\band\b',payload) if x.strip()]
        known={x.casefold() for x in _GENERIC_HIDDEN_LEAD_TOPICS}
        if parts and all(x in known for x in parts):
            return True
    # Older preliminary summaries commonly appended the same generic outreach angle.
    if low.startswith('specializes in ') and 'explore whether ' in low:
        base=first
        for a in _GENERIC_HIDDEN_LEAD_CONTEXTS:
            if a.casefold() in base:
                return True
    return False


def _summary_duplicate_for_other_company(summary, company=''):
    text=re.sub(r'\s+',' ',str(summary or '')).strip()
    if not text or hidden_lead_summary_is_generic(text):
        return False
    try:
        qs=CompanyLead.objects.filter(user_deleted=False,summary__iexact=text)
        if str(company or '').strip():
            qs=qs.exclude(company__iexact=str(company).strip())
        return qs.exists()
    except Exception:
        return False


def _specific_company_summary_candidate(summary, company=''):
    # Section labels such as [APPLICATION] and [PAGE_TITLE] are provenance metadata,
    # but the prose after them can still be useful. Strip the labels instead of throwing
    # away an otherwise readable company/technical description.
    clean=strip_hidden_lead_evidence_markers(summary)
    clean=_naturalize_lead_summary(clean,company)
    if not clean or hidden_lead_summary_is_generic(clean):
        return ''
    if _summary_duplicate_for_other_company(clean,company):
        return ''
    return clean[:1600]


def market_summary_needs_refresh(summary):
    """Return True for blank, legacy, generic, or old labelled Hidden Leads summaries."""
    text=re.sub(r'\s+',' ',str(summary or '')).strip()
    low=text.lower()
    if not text:
        return True
    if hidden_lead_summary_is_generic(text):
        return True
    if hidden_lead_summary_has_evidence_markers(text):
        return True
    enum_text=re.sub(r'[_-]+',' ',low)
    enum_text=re.sub(r'\s+',' ',enum_text).strip(' .,:;')
    if enum_text in {'full time','part time','contract','contractor','collaboration','agency consulting','one time project','unknown','fully remote','remote','hybrid','onsite','on site'}:
        return True
    # v0.8.20-v0.8.22 used visibly templated labels. Rebuild those into natural prose.
    if any(marker in low for marker in ('why selected:', 'potential use:', 'products/services:')):
        return True
    if re.match(r'^(?:[-*•]\s+|\d+[.)]\s+)', text):
        return True
    if low.startswith(('the organization ', 'the company ', 'this organization ', 'this company ')):
        return True
    # Very short or single-fragment historical summaries are usually polished search/page snippets.
    if len(text.split()) < 18:
        return True
    return False


def _organization_context(text):
    """Return conservative business/product categories inferred from public page evidence."""
    blob=' '+re.sub(r'\s+',' ',str(text or '')).lower()+' '
    labels=[]
    rules=[
        ('engineering and product-development services',('engineering services','product development','design services','development services','engineering consultancy','engineering consulting')),
        ('embedded software or firmware products',('embedded product','embedded software','firmware product','firmware platform','embedded platform')),
        ('software platforms and developer tools',('software platform','developer tool','development tool','software tool','toolchain','sdk','platform software')),
        ('hardware and electronics systems',('hardware product','electronics product','electronic product','board design','hardware design','single-board','embedded hardware')),
        ('industrial or IoT systems',('industrial iot','industrial system','iot product','iot platform','connected device')),
        ('emulation and virtualization technology',('emulation','emulator','virtualization','virtualisation','qemu')),
        ('legacy modernization, migration or porting',('legacy modernization','legacy modernisation','software migration','system migration','porting service','porting services','compatibility engineering')),
    ]
    for label,needles in rules:
        if any(n in blob for n in needles):
            labels.append(label)
        if len(labels)>=2:
            break
    return labels


def _clean_summary_sentence(text, company=''):
    clean=re.sub(r'\s+',' ',str(text or '')).strip().strip('"')
    clean=re.sub(r'(?i)^(summary|description)\s*:\s*','',clean)
    if company:
        clean=re.sub(r'(?i)^'+re.escape(company.strip())+r'\s+(?:is|are|works on|specialises in|specializes in|develops|builds|provides|offers)\s+', '', clean).strip()
    return clean


def _naturalize_lead_summary(text, company=''):
    clean=re.sub(r'\s+',' ',str(text or '')).strip().strip('"')
    clean=re.sub(r'^(?:[-*•]\s*|\d+[.)]\s*)+','',clean).strip()
    clean=re.sub(r'(?i)\b(?:why selected|potential use|products/services)\s*:\s*','',clean)
    if company:
        # Company is already a separate list-view column; do not waste summary space repeating it.
        clean=re.sub(r'(?i)^'+re.escape(company.strip())+r'\s+(?:is|are|specialises in|specializes in|develops|builds|provides|offers|focuses on)\s+', '', clean).strip()
    starts=[
        (r'(?i)^the (?:organization|company) (?:specialises|specializes) in\s+', 'Specializes in '),
        (r'(?i)^this (?:organization|company) (?:specialises|specializes) in\s+', 'Specializes in '),
        (r'(?i)^the (?:organization|company) (?:develops|builds)\s+', 'Develops '),
        (r'(?i)^the (?:organization|company) (?:offers|provides)\s+', 'Provides '),
        (r'(?i)^the (?:organization|company) focuses on\s+', 'Focuses on '),
    ]
    for pat,repl in starts:
        if re.search(pat,clean):
            clean=re.sub(pat,repl,clean); break
    # Remove accidental numbered second sentence too.
    clean=re.sub(r'(?<=[.!?])\s+(?:[-*•]\s*|\d+[.)]\s*)+', ' ', clean)
    return clean.strip()


def _evidence_summary_fallback(company,title,text,max_words=58):
    """Select compact business prose without leaking structured evidence labels."""
    segments=_company_summary_evidence_segments(text)
    if not segments:
        return ''
    candidates=[]
    for section,segment in segments:
        clean=re.sub(r'\s+',' ',str(segment or '')).strip()
        if not clean:
            continue
        for sent in re.split(r'(?<=[.!?])\s+', clean[:9000]):
            sent=_clean_summary_sentence(sent,company)
            if hidden_lead_summary_has_evidence_markers(sent):
                continue
            words=sent.split(); low=' '+sent.lower()+' '
            if not (8 <= len(words) <= 45):
                continue
            if any(x in low for x in (' cookie ', ' privacy policy ', ' sign in ', ' log in ', ' subscribe ', ' all rights reserved ', ' job opening ', ' apply now ')):
                continue
            strong_business=any(v in low for v in (' develops ', ' builds ', ' provides ', ' offers ', ' creates ', ' maintains ', ' designs ', ' supports ', ' specialises ', ' specializes ', ' focuses on ', ' manufactures ', ' sells '))
            score=4 if strong_business else 0
            if any(v in low for v in (' platform ', ' product ', ' service ', ' project ', ' tool ', ' device ', ' system ')):
                score+=2
            if any(v in low for v in (' software ', ' hardware ', ' firmware ', ' engineering ')):
                score+=1
            score+=min(2,len(_summary_topics(sent)))
            if title and any(tok.lower() in low for tok in re.findall(r'[A-Za-z][A-Za-z0-9+-]{3,}', title)[:5]):
                score+=1
            # A PAGE_TITLE section often contains article/tutorial prose. Require an actual
            # organization/product signal before using it as company-summary evidence.
            if section=='PAGE_TITLE' and not strong_business and score<4:
                continue
            if score>=3:
                candidates.append((score,sent))
            if len(candidates)>=10:
                break
        if len(candidates)>=10:
            break
    candidates.sort(key=lambda x:x[0],reverse=True)
    if not candidates:
        return ''
    result=candidates[0][1].strip()
    words=result.split()
    if len(words)>max_words: result=' '.join(words[:max_words]).rstrip(' ,.;:')+'…'
    elif result and result[-1] not in '.!?': result+='.'
    return result[:900]


def _named_offerings(text, title=''):
    """Extract a few conservatively named products/platforms/services from first-party-style phrasing."""
    src=re.sub(r'\s+',' ',str(text or '')).strip()[:14000]
    found=[]
    patterns=[
        r'(?i:\b(?:our|the)\s+(?:flagship\s+)?(?:product|platform|tool|solution|service|device|system)\s+(?:is|called|named)?\s*)["“]?([A-Z][A-Za-z0-9+._-]*(?:\s+[A-Z][A-Za-z0-9+._-]*){0,3})',
        r'(?i:\b(?:we|our team|the company)\s+(?:build|develop|maintain|make|offer|provide)s?\s+)["“]?([A-Z][A-Za-z0-9+._-]*(?:\s+[A-Z][A-Za-z0-9+._-]*){0,3})',
        r'(?i:\b(?:products?|platforms?|tools?|solutions?|services?)\s+(?:include|such as|like)\s+)["“]?([A-Z][A-Za-z0-9+._-]*(?:\s+[A-Z][A-Za-z0-9+._-]*){0,3})',
        r'(?i:\b(?:introducing|meet)\s+)["“]?([A-Z][A-Za-z0-9+._-]*(?:\s+[A-Z][A-Za-z0-9+._-]*){0,3})',
    ]
    for pat in patterns:
        for m in re.finditer(pat,src):
            name=re.sub(r'\s+',' ',m.group(1)).strip(' .,:;"“”')
            low=name.lower()
            if len(name)<2 or low in {'software','hardware','engineering','services','solutions','products','platform','technology','systems'}: continue
            if name not in found: found.append(name)
            if len(found)>=2: return found
    # Do not infer a product name from the page title alone. Search-result and article
    # titles are frequently descriptive headlines, which previously produced summaries
    # that treated random page text as a company product.
    return found[:2]


def _summary_action(topics):
    low={str(x).lower() for x in topics}
    actions=[]
    mapping=[
        ('reverse engineering','compatibility analysis and legacy-system investigation'),
        ('binary analysis','binary tooling and low-level diagnostics'),
        ('firmware','firmware integration and maintenance'),
        ('embedded systems','embedded integration and product engineering'),
        ('device drivers','driver and board-support work'),
        ('emulation','emulator integration and validation'),
        ('virtualization','virtual-platform integration and compatibility'),
        ('legacy systems','porting and modernization'),
        ('protocols','protocol integration and interoperability'),
        ('hardware bring-up','board bring-up and hardware/software integration'),
        ('GPU computing','GPU acceleration and low-level compute integration'),('AI systems','AI inference integration and systems optimization'),
    ]
    for key,label in mapping:
        if key in low and label not in actions: actions.append(label)
        if len(actions)>=2: break
    return actions or ['embedded and low-level product engineering']


def short_company_summary(company,title,text,company_intel=None):
    """Return a natural, evidence-grounded and company-specific Hidden Leads summary."""
    src=re.sub(r'\s+',' ',str(text or '')).strip()[:16000]
    if not src: return ''
    profile=Profile.objects.get_or_create(pk=1)[0]
    priorities=re.sub(r'\s+',' ',str(profile.high_priority_text or '')).strip()[:1800]
    offerings=_named_offerings(src,title)
    contexts=_organization_context(src)[:2]
    retained=company_summary_from_intel(company_intel or {},1200)
    evidence_hints=[]
    if retained: evidence_hints.append('Retained verified company facts: '+retained+'.')
    if offerings: evidence_hints.append('Named offerings detected in the evidence: '+', '.join(offerings[:2])+'.')
    if contexts: evidence_hints.append('Broad context only (do not use this alone as the summary): '+'; '.join(contexts)+'.')
    try:
        out=generate(
            "Summarize the supplied public evidence in about 45 to 90 words using only facts supported by that evidence. "
            "The company name is already shown in the table, so do not begin by repeating it. "
            "Write one or two natural sentences with no numbering, bullets, headings, labels, score language, or phrases such as 'Why selected', 'Potential use', 'candidate profile', or 'do not assume an open role'. Start directly with a useful verb phrase such as 'Develops…', 'Builds…', 'Provides…', 'Focuses on…' or 'Specializes in…'; do not start with the company name or 'The organization/company'. "
            "The first sentence must explain what this specific organization actually makes, develops, sells, maintains, or provides. Prefer one or two NAMED products, platforms, tools, devices, services, or projects when first-party evidence clearly names them. If no product name is supported, use another concrete differentiating fact from the evidence. Do not answer with a broad reusable taxonomy sentence such as 'Specializes in emulation and virtualization technology' or 'Specializes in software platforms and developer tools'. If the evidence cannot support a company-specific description, return exactly SUMMARY_PENDING. "
            "If a second sentence is useful, add a company-specific technical detail or practical outreach angle that follows from that product/service context. Do not claim a vacancy, budget, contract, customer relationship, or hiring intent. "
            "Avoid keyword lists. Do not repeat the same technology or phrase across both sentences; pick the strongest technical connection once, then describe the useful work in different words. Do not polish or quote a random webpage sentence. "
            "If the material is mainly a forum/support thread, personal blog, news/editorial/comparison/review site, documentation/reference/project site, generic community, or job aggregator rather than a plausible organization/customer lead, return exactly NOT_A_QUALIFYING_ORGANIZATION. "
            + (' '.join(evidence_hints)+' ' if evidence_hints else '')
            + f"Candidate priorities (context only; never mention them explicitly): {priorities or 'embedded and low-level software specialist work'}. Organization: {company}. Page title: {title}. Evidence: {src}",
            stage='page_summarization',timeout=45,
        ).strip()
        if 'NOT_A_QUALIFYING_ORGANIZATION' in out.upper(): return ''
        if 'SUMMARY_PENDING' in out.upper(): return preliminary_company_summary(company,title,src,[],company_intel=company_intel)
        clean=_naturalize_lead_summary(out,company)
        sentences=[x.strip() for x in re.split(r'(?<=[.!?])\s+',clean) if x.strip()]
        clean=' '.join(sentences[:2]).strip()
        words=clean.split()
        if len(words)>95: clean=' '.join(words[:95]).rstrip(' ,.;:')+'…'
        low=clean.lower()
        offerings_present=(not offerings) or any(off.lower() in low for off in offerings[:2])
        candidate=_specific_company_summary_candidate(clean,company)
        if candidate and len(candidate.split())>=12 and offerings_present and not any(x in low for x in ('why selected:','potential use:','candidate profile')):
            return candidate
    except CloudLimitReached:
        raise
    except Exception:
        pass
    return preliminary_company_summary(company,title,src,[],company_intel=company_intel)


def preliminary_company_summary(company,title,text,hits=None,company_intel=None):
    """Immediate deterministic company-specific note while AI refinement runs."""
    topics=[]
    for value in (hits or [])+_summary_topics(text):
        value=str(value or '').strip()
        if value and value.lower() not in {x.lower() for x in topics}: topics.append(value)
    topics=topics[:4]
    retained=company_summary_from_intel(company_intel or {},1200)
    candidate=_specific_company_summary_candidate(retained,company) if retained else ''
    if candidate:
        return candidate[:1400]
    offerings=_named_offerings(text,title)
    if offerings:
        named=' and '.join(offerings[:2])
        candidate=_specific_company_summary_candidate(f"Develops or offers {named}.",company)
        if candidate:
            return candidate[:1400]
    # Prefer a factual sentence taken from retained evidence over a broad taxonomy label.
    # The previous context-only fallback generated the exact same description for unrelated
    # companies (for example "Specializes in emulation and virtualization technology").
    factual=_evidence_summary_fallback(company,title,text,max_words=48)
    candidate=_specific_company_summary_candidate(factual,company) if factual else ''
    if candidate:
        return candidate[:1400]
    return ''


def is_general_market_host(url):
    try:
        host=urllib.parse.urlparse(str(url or '')).netloc.lower().split('@')[-1].split(':')[0].removeprefix('www.')
    except Exception:
        return False
    labels={x for x in host.split('.') if x}
    return is_job_platform_host(host) or any(host==d or host.endswith('.'+d) for d in GENERAL_PLATFORM_HOSTS) or bool(labels.intersection(GENERAL_PLATFORM_BRANDS))


def is_general_market_company(name):
    key=re.sub(r'[^a-z0-9]+','',str(name or '').lower())
    return is_platform_company_name(name) or key in {re.sub(r'[^a-z0-9]+','',x) for x in GENERAL_PLATFORM_COMPANIES}


def _providers(limit=4):
    # Reuse the same seven-day retained-yield/error routing as campaign discovery. Hidden
    # Leads should not spend most of its scan on engines that are already demonstrating
    # severe errors or sustained zero retained yield.
    rows,_details=provider_selection_details(limit=limit,preferred_only=True)
    return rows


def _terms():
    profile=build_search_profile()
    terms=[x.get('term') for x in profile.get('skills',[]) if x.get('term')]
    roles=[x.get('role') for x in profile.get('role_families',[]) if x.get('role')]
    # Keep the old niche-discovery families in every scan rather than letting a long
    # CV/profile list push them beyond a fixed slice. These are intentionally broad
    # enough to rediscover the SDR/emulator/firmware companies Hidden Leads is for.
    fallback=['software defined radio','SDR','QEMU','emulator','emulation','reverse engineering','legacy systems','embedded Linux','firmware','device drivers','BSP','bootloader','VoIP','SIP','DOS','BIOS','protocol analyzer']
    ordered=[]
    for value in list(terms[:22])+list(roles[:8])+fallback:
        value=str(value or '').strip()
        if value and value.casefold() not in {x.casefold() for x in ordered}:
            ordered.append(value)
    return ordered[:44]


def _hidden_lead_organization_signal(company, blob, technical_hits=0, activity_hits=0):
    """Return True only when a Hidden Lead page looks like a first-party organization.

    Search-engine keyword overlap is not enough: articles, community pages and personal
    technical posts often mention the same niche terms.  Prefer explicit first-party
    product/service language or a company-named page with organization/activity evidence.
    """
    text=str(blob or '').casefold()
    strong_markers=(
        'our product','our products','our services','our platform','our solutions',
        'we develop','we build','we provide','we design','we make','we create',
        'engineering services','consulting services','contact sales','request a demo',
        'our customers','our clients','what we do','who we are','we specialize','we specialise',
    )
    organization_markers=(
        'about us','our team','our company','founded','headquartered','our offices',
        'customers','clients','products','services','solutions','company profile','contact us',
    )
    if any(marker in text for marker in strong_markers):
        return True
    words=[w for w in re.findall(r'[a-z0-9]+',str(company or '').casefold()) if len(w)>=4 and w not in {'company','technologies','technology','solutions','systems','group','labs'}]
    company_named=bool(words and any(w in text for w in words[:4]))
    org_hits=sum(1 for marker in organization_markers if marker in text)
    if company_named and (org_hits>=1 or (int(activity_hits or 0)>=1 and int(technical_hits or 0)>=2)):
        return True
    return bool(org_hits>=2 and int(activity_hits or 0)>=1)




_EDITORIAL_DISCOVERY_HOSTS=(
    'hackaday.com','tomshardware.com','arstechnica.com','theverge.com','theregister.com',
    'makezine.com','hackster.io','eejournal.com','embedded.com','electronicsweekly.com',
)
_ORG_PATH_HINTS=('about','company','products','product','solutions','services','contact','team','who-we-are','what-we-do')
_NICHE_TECH_MARKERS=(
    'software defined radio','sdr','emulator','emulation','qemu','firmware','embedded linux','bsp',
    'board support package','reverse engineering','bootloader','device driver','fpga','voip','sip',
    'legacy system','retro computing','protocol analyzer','hardware bring-up','jtag','uart','can bus',
)
_SALVAGE_POSITIVE_MARKERS=(
    'expired','closed','filled','no longer','unavailable','not available','location','geograph','region',
    'remote','onsite','on-site','hybrid','timezone','time zone','shipping','hardware','equipment',
    'cannot verify','could not verify','not found','404','410','employment','contract','availability',
    'experience','certification','certificate','industry','banking','stack','requirement',
)
_SALVAGE_NEGATIVE_MARKERS=(
    'blacklist','blacklisted','scam','fraud','adult content','spam','malware','irrelevant company',
    'wrong company','invalid company','job board','aggregator','recruitment agency','staffing agency',
)


def _is_editorial_discovery_host(url_or_host):
    host=source_domain(url_or_host) if '://' in str(url_or_host or '') else str(url_or_host or '').lower().removeprefix('www.')
    return any(host==d or host.endswith('.'+d) for d in _EDITORIAL_DISCOVERY_HOSTS)


_OUTREACH_STRONG_SIGNALS=(
    ('contact_sales','contact sales'),('request_quote','request a quote'),('request_proposal','request a proposal'),
    ('rfp','request for proposal'),('tender','tender'),('contract_engineering','contract engineering'),
    ('engineering_services','engineering services'),('consulting_services','consulting services'),
    ('custom_engineering','custom engineering'),('professional_services','professional services'),
    ('outsourcing','outsourcing'),('implementation_partner','implementation partner'),
    ('technology_partner','technology partner'),('partner_with_us','partner with us'),
    ('schedule_consultation','schedule a consultation'),('project_inquiry','project inquiry'),
    ('talk_to_sales','talk to sales'),('request_demo','request a demo'),('vendor_registration','vendor registration'),
)
_OUTREACH_HIRING_SIGNALS=(
    ('we_are_hiring','we are hiring'),('join_our_team','join our team'),('open_roles','open roles'),
    ('open_positions','open positions'),('hiring_engineers','hiring engineers'),('careers','careers'),
)
_OUTREACH_COMMERCIAL_SIGNALS=(
    ('services','our services'),('solutions','our solutions'),('consulting','consulting'),
    ('customers','our customers'),('clients','our clients'),('integration','integration services'),
    ('support','support services'),('projects','client projects'),('partnerships','partnerships'),
)


def _hidden_lead_outreach_signal(blob, *, contactable=False, provenance='discovered_company'):
    """Return deterministic evidence that there is a practical reason to contact a lead.

    CV/technical keyword overlap is deliberately excluded. A Hidden Lead needs a current
    commercial, partnership, consulting, contractor or hiring signal in addition to being
    technically relevant. A rejected Opportunity is itself evidence of active hiring, so
    salvage receives a bounded baseline rather than being treated like a random web page.
    """
    text=' '.join(str(blob or '').casefold().split())[:36000]
    matched=[]; score=0
    strong=[]
    for label,phrase in _OUTREACH_STRONG_SIGNALS:
        if phrase in text:
            strong.append(label)
    if strong:
        score+=min(6,3+max(0,len(strong)-1))
        matched.extend(strong[:8])
    hiring=[]
    for label,phrase in _OUTREACH_HIRING_SIGNALS:
        if phrase in text:
            hiring.append(label)
    if hiring:
        score+=2
        matched.extend(hiring[:4])
    commercial=[]
    for label,phrase in _OUTREACH_COMMERCIAL_SIGNALS:
        if phrase in text:
            commercial.append(label)
    if commercial:
        score+=1
        matched.extend(commercial[:5])
    if contactable:
        score+=1; matched.append('contact_path')
    if provenance=='salvaged_opportunity':
        # A recently rejected/suppressed vacancy proves that the organization is actively
        # hiring; this is a legitimate company-level outreach signal even when the vacancy
        # itself was unsuitable for the candidate.
        score=max(score,3); matched.append('recent_hiring_opportunity')
    return {'score':min(10,int(score)),'signals':list(dict.fromkeys(matched))[:12],
            'strong_count':len(strong),'hiring_count':len(hiring),'commercial_count':len(commercial),
            'contactable':bool(contactable),'provenance':provenance}


def _hidden_lead_score(company, blob, hits, activity, *, organization_confidence=0, contactable=False, provenance='discovered_company'):
    """Return a richer Hidden Lead score and its component explanation.

    The score intentionally values unusual technical evidence separately from company
    verification.  This prevents a niche engineering article from being discarded merely
    because the article itself does not contain corporate boilerplate.
    """
    text=str(blob or '').casefold()
    niche=sum(1 for marker in _NICHE_TECH_MARKERS if marker in text)
    technical=min(100,38+min(42,len(hits)*9)+min(20,len(activity)*5)+min(12,niche*4))
    company_conf=max(0,min(100,int(organization_confidence or 0)))
    contactability=75 if contactable else (45 if any(x in text for x in ('contact us','contact sales','mailto:','@')) else 25)
    uniqueness=min(100,45+niche*9+min(20,len(activity)*3))
    commercial=min(100,35+(18 if any(x in text for x in ('product','products','services','consulting','customers','clients','platform','solutions')) else 0)+(12 if contactability>=45 else 0)+(10 if provenance=='salvaged_opportunity' else 0))
    outreach=_hidden_lead_outreach_signal(text,contactable=contactable,provenance=provenance)
    outreach_strength=min(100,int(outreach.get('score') or 0)*20)
    # Technical similarity is still important, but no longer dominates the score. The
    # practical outreach signal now carries enough weight to distinguish a sales lead from
    # an arbitrary technically related company/article.
    total=round(0.30*technical+0.22*company_conf+0.08*contactability+0.10*uniqueness+0.10*commercial+0.20*outreach_strength)
    return max(25,min(98,int(total))),{
        'technical_relevance':technical,'company_confidence':company_conf,'contactability':contactability,
        'uniqueness':uniqueness,'commercial_plausibility':commercial,'outreach_signal':outreach,
        'niche_markers':niche,'provenance_type':provenance,
    }


def _same_domain_links(inspected, domain):
    rows=[]; seen=set()
    for item in (inspected or {}).get('links') or []:
        if not isinstance(item,dict):
            continue
        url=str(item.get('url') or '').strip()
        if not url or registrable_domain(url)!=domain:
            continue
        path=(urllib.parse.urlparse(url).path or '').casefold()
        anchor=(str(item.get('anchor') or '')+' '+str(item.get('context') or '')).casefold()
        if not any(h in path or h.replace('-',' ') in anchor for h in _ORG_PATH_HINTS):
            continue
        clean=url.split('#',1)[0]
        if clean in seen:
            continue
        seen.add(clean); rows.append(clean)
    return rows




def _retained_company_corroboration(company, target=''):
    """Use already-retained ScoutBox company evidence without network or AI calls."""
    company=' '.join(str(company or '').split()).strip()
    if not company or not is_plausible_company_name(company):
        return None
    try:
        summary,intel=stored_company_context(company,'',str(target or ''))
    except Exception:
        return None
    confidence=0
    try: confidence=int((intel or {}).get('confidence') or 0)
    except Exception: confidence=0
    facts=(intel or {}).get('facts') if isinstance(intel,dict) else []
    sources=(intel or {}).get('sources') if isinstance(intel,dict) else []
    credible=company_info_has_display_data(intel) or bool(str(summary or '').strip() and (confidence>=50 or len(facts or [])>=2 or len(sources or [])>=1))
    if not credible:
        return None
    return {
        'verified':True,'company':company,'confidence':max(72,min(90,confidence or 78)),'reason':'retained_company_context',
        'pages':[],'text':str(summary or '')[:12000],'contact_url':'',
    }

def _corroborate_hidden_lead_organization(target, company='', *, inspected=None, initial_title='', initial_text='', max_pages=2):
    """Verify that a technically interesting page belongs to a real organization.

    The discovery page and the organization-verification page may be different pages on
    the same registrable domain.  Only a small bounded number of pages are fetched.
    """
    domain=registrable_domain(target)
    if not domain or is_job_platform_host(domain) or is_general_market_host('https://'+domain):
        return {'verified':False,'company':company,'confidence':0,'reason':'platform_or_missing_domain','pages':[]}
    candidate=' '.join(str(company or '').split()).strip()
    initial_blob=(' '+str(initial_title or '')+' '+str(initial_text or '')).strip()
    retained=_retained_company_corroboration(candidate,target)
    if retained:
        retained['text']=(' '.join(x for x in (retained.get('text',''),initial_blob) if x))[:24000]
        return retained
    initial_low=initial_blob.casefold()
    explicit_first_party=any(marker in initial_low for marker in (
        'our product','our products','our services','our platform','our solutions','we develop','we build','we design','we manufacture','contact sales','our customers','our clients','what we do','who we are'
    ))
    if candidate and is_plausible_company_name(candidate) and explicit_first_party:
        return {'verified':True,'company':candidate,'confidence':82,'reason':'explicit_first_party_discovery_page','pages':[target],'text':initial_blob[:18000],'contact_url':''}
    parsed=urllib.parse.urlparse(str(target or ''))
    root=f'{parsed.scheme or "https"}://{domain}/'
    queue=[root]+_same_domain_links(inspected,domain)
    combined=[initial_blob]
    pages=[]; contact_url=''; best_company=candidate; seen=set()
    page_cap=max(1,int(max_pages or 2))
    while queue and len(pages)<page_cap:
        url=queue.pop(0)
        clean=str(url or '').split('#',1)[0]
        if not clean or clean in seen:
            continue
        seen.add(clean)
        fetched=fetch_target(clean,timeout=10)
        if not fetched.get('ok'):
            continue
        final=str(fetched.get('target_url') or clean)
        if registrable_domain(final)!=domain:
            continue
        pages.append(final)
        title=str(fetched.get('title') or '')
        text=str(fetched.get('text') or '')[:14000]
        combined.append(title+' '+text)
        if not best_company or not is_plausible_company_name(best_company):
            recovered=display_company_name(company_from_page(final,title,text),final)
            if is_plausible_company_name(recovered):
                best_company=recovered
        path=(urllib.parse.urlparse(final).path or '').casefold()
        if 'contact' in path and not contact_url:
            contact_url=final
        # A root/product page can reveal the real About/Contact page. Follow only enough
        # same-domain organization links to fill the small corroboration budget.
        for extra in _same_domain_links(fetched,domain):
            extra_clean=str(extra or '').split('#',1)[0]
            if extra_clean and extra_clean not in seen and extra_clean not in queue:
                queue.append(extra_clean)
    blob=' '.join(combined)
    org_markers=sum(1 for marker in ('about us','our company','our team','products','services','solutions','customers','clients','contact us','founded','headquartered') if marker in blob.casefold())
    strong=_hidden_lead_organization_signal(best_company,blob,technical_hits=2,activity_hits=1)
    # Corroboration must add at least one organization-specific signal. This keeps a
    # technical personal blog from qualifying merely because its posts mention niche work.
    verified=bool(best_company and is_plausible_company_name(best_company) and ((strong and org_markers>=1) or org_markers>=2))
    confidence=min(96,55+org_markers*8+(12 if strong else 0)+(8 if pages else 0)) if verified else min(54,org_markers*10)
    return {'verified':verified,'company':best_company,'confidence':confidence,'reason':('same_domain_company_corroboration' if verified else 'weak_organization'),'pages':pages,'text':blob[:24000],'contact_url':contact_url}



# ScoutBox 0.11.8 Hidden Lead admission gate -------------------------------------------------
# Hidden Leads are company/outreach records, not a place for every page that mentions a
# relevant keyword.  This bounded minibrowser reviews the candidate URL plus a few first-
# party organization pages before a Hidden Lead is admitted.  The LLM returns a score and
# code enforces the cutoff; failures default to review/reject rather than silently creating
# a junk lead.
_LEAD_MINIBROWSER_PATH_HINTS=(
    'about','about-us','company','who-we-are','what-we-do','services','solutions','products','contact','contact-us','team','careers','jobs'
)
_LEAD_MINIBROWSER_REJECT_PURPOSES={'content_only','directory','job_board','documentation','marketplace','news_article','generic_tool_page','other'}
_LEAD_MINIBROWSER_ADMIT_CUTOFF=75
_LEAD_MINIBROWSER_REVIEW_CUTOFF=55


def _hidden_lead_json_object(text):
    raw=str(text or '').strip()
    candidates=[raw]
    m=re.search(r'```(?:json)?\s*(.*?)```',raw,re.I|re.S)
    if m:
        candidates.insert(0,m.group(1).strip())
    first=raw.find('{'); last=raw.rfind('}')
    if first>=0 and last>first:
        candidates.append(raw[first:last+1])
    for item in candidates:
        try:
            parsed=json.loads(item)
            if isinstance(parsed,dict):
                return parsed
        except Exception:
            pass
    return {}


def _hidden_lead_abs_url(root, href):
    href=str(href or '').strip()
    if not href or href.startswith(('mailto:','tel:','javascript:','#')):
        return ''
    try:
        return urllib.parse.urljoin(root,href).split('#',1)[0]
    except Exception:
        return ''


def _hidden_lead_pick_minibrowser_links(fetched, domain, root):
    rows=[]
    for item in (fetched or {}).get('links') or []:
        if not isinstance(item,dict):
            continue
        url=_hidden_lead_abs_url(root,item.get('url'))
        if not url or registrable_domain(url)!=domain:
            continue
        path=(urllib.parse.urlparse(url).path or '').strip('/').casefold()
        anchor=(str(item.get('anchor') or '')+' '+str(item.get('context') or '')).casefold()
        joined=' '.join([path.replace('-',' '),anchor])
        score=0
        for idx,hint in enumerate(_LEAD_MINIBROWSER_PATH_HINTS):
            norm=hint.replace('-',' ')
            if hint in path or norm in joined:
                score+=20-idx
        if score>0:
            rows.append((score,url))
    rows.sort(key=lambda x:(-x[0],len(x[1])))
    out=[]
    for _score,url in rows:
        if url not in out:
            out.append(url)
        if len(out)>=8:
            break
    return out


def hidden_lead_minibrowser_collect(url, company='', *, inspected=None, initial_title='', initial_text='', max_pages=6, deadline_at=None, page_timeout=6):
    """Fetch a bounded first-party page set for Hidden Lead admission.

    Returns no model decision.  It is safe to call before persistence; it only fetches a
    small same-domain page set and prepares compact evidence for the LLM gate.
    """
    domain=registrable_domain(url)
    if not domain or is_job_platform_host(domain) or is_general_market_host('https://'+domain):
        return {'ok':False,'reason':'platform_or_missing_domain','domain':domain,'pages':[],'text':''}
    parsed=urllib.parse.urlparse(str(url or ''))
    root=f'{parsed.scheme or "https"}://{domain}/'
    candidates=[]
    for u in (url,root):
        u=str(u or '').split('#',1)[0]
        if u and u not in candidates:
            candidates.append(u)
    first=inspected if isinstance(inspected,dict) else None
    if first:
        candidates.extend(_hidden_lead_pick_minibrowser_links(first,domain,root))
    for path in ('about','about-us','company','services','solutions','products','contact','contact-us','team','careers','jobs'):
        u=urllib.parse.urljoin(root,path)
        if u not in candidates:
            candidates.append(u)
    seen=set(); pages=[]; chunks=[]; contact_url=''; best_company=' '.join(str(company or '').split()).strip()
    if initial_title or initial_text:
        chunks.append('[SOURCE_URL]\n'+str(url or '')+'\n[TITLE]\n'+str(initial_title or '')[:300]+'\n[TEXT]\n'+str(initial_text or '')[:8000])
    cap=max(1,min(8,int(max_pages or 6)))
    timed_out=False
    def _time_left():
        if deadline_at is None:
            return None
        try:
            return float(deadline_at) - time.monotonic()
        except Exception:
            return None
    for cand in candidates:
        left=_time_left()
        if left is not None and left <= 1.0:
            timed_out=True
            break
        clean=str(cand or '').split('#',1)[0]
        if not clean or clean in seen or registrable_domain(clean)!=domain:
            continue
        seen.add(clean)
        fetched=first if first and clean.rstrip('/')==str((first.get('target_url') or url) or '').split('#',1)[0].rstrip('/') else None
        if fetched is None:
            left=_time_left()
            if left is not None and left <= 1.0:
                timed_out=True
                break
            fetched=fetch_target(clean,timeout=max(2,min(int(page_timeout or 6),int(left or page_timeout or 6))))
        if not fetched.get('ok'):
            continue
        final=str(fetched.get('target_url') or clean).split('#',1)[0]
        if registrable_domain(final)!=domain:
            continue
        title=str(fetched.get('title') or '')[:300]
        text=' '.join(str(fetched.get('text') or '').split())[:9000]
        if not text and not title:
            continue
        if final not in pages:
            pages.append(final)
        if 'contact' in (urllib.parse.urlparse(final).path or '').casefold() and not contact_url:
            contact_url=final
        if not best_company or not is_plausible_company_name(best_company):
            recovered=display_company_name(company_from_page(final,title,text),final)
            if is_plausible_company_name(recovered):
                best_company=recovered
        label='PAGE_'+str(len(pages))
        chunks.append(f'[{label}]\nURL: {final}\nTITLE: {title}\nTEXT: {text}')
        if len(pages)>=cap:
            break
        # Newly fetched root/about pages may expose a better contact/about link.
        for extra in _hidden_lead_pick_minibrowser_links(fetched,domain,root):
            if extra not in seen and extra not in candidates:
                candidates.append(extra)
    blob='\n\n'.join(chunks)[:36000]
    reason='timeout' if timed_out else ('collected' if (pages or blob) else 'no_fetchable_pages')
    return {'ok':bool(pages or blob),'reason':reason,'timed_out':bool(timed_out),'domain':domain,'company':best_company,'pages':pages[:cap],'contact_url':contact_url,'text':blob}


def hidden_lead_minibrowser_admission(campaign, url, company='', *, inspected=None, initial_title='', initial_text='', evidence='', hits=None, max_pages=6, cutoff=None, deadline_seconds=None, deadline_at=None, page_timeout=6):
    """LLM-backed pre-persistence admission gate for Hidden Leads only.

    A lead is admitted only when the minibrowser evidence shows a real organization with
    a practical reason for this user to contact or track it.  The LLM can recommend
    admit/review/reject, but code enforces the numeric cutoff.
    """
    hits=list(hits or [])[:12]
    if deadline_at is None and deadline_seconds:
        try:
            deadline_at=time.monotonic()+float(deadline_seconds)
        except Exception:
            deadline_at=None
    def _remaining(default=30):
        if deadline_at is None:
            return default
        try:
            return max(0.0,float(deadline_at)-time.monotonic())
        except Exception:
            return default
    review=hidden_lead_minibrowser_collect(url,company,inspected=inspected,initial_title=initial_title,initial_text='\n'.join([str(initial_text or ''),str(evidence or '')])[:18000],max_pages=max_pages,deadline_at=deadline_at,page_timeout=page_timeout)
    if not review.get('ok'):
        review.update({'decision':'reject','lead_score':0,'admit':False,'review':False,'cutoff':cutoff or _LEAD_MINIBROWSER_ADMIT_CUTOFF})
        return review
    lead_rules=lead_policy(selectivity_current('hidden_leads'))
    contactable=bool(review.get('contact_url') or _THIRD_PARTY_EMAIL_RE.search(str(review.get('text') or '')))
    outreach=_hidden_lead_outreach_signal(review.get('text') or '',contactable=contactable,provenance='discovered_company')
    review['outreach_signal']=outreach
    outreach_min=int(lead_rules.get('outreach_signal_min') or 3)
    if int(outreach.get('score') or 0) < outreach_min:
        review.update({'decision':'reject','lead_score':0,'admit':False,'review':False,
                       'cutoff':cutoff or _LEAD_MINIBROWSER_ADMIT_CUTOFF,
                       'reason':'Insufficient current outreach/commercial signal; technical relevance alone is not a Hidden Lead.',
                       'source':'0.11.116_hidden_lead_outreach_gate'})
        return review
    if _remaining(30) <= 5:
        review.update({'decision':'review','lead_score':0,'admit':False,'review':True,'cutoff':cutoff or _LEAD_MINIBROWSER_ADMIT_CUTOFF,'timeout':True,'reason':'Minibrowser evidence collection exhausted the per-lead reassessment budget.'})
        return review
    profile=Profile.objects.get_or_create(pk=1)[0]
    campaign_scope={
        'campaign_roles':str(getattr(campaign,'role_families','') or '')[:1000] if campaign else '',
        'campaign_technologies':str(getattr(campaign,'technologies','') or '')[:1000] if campaign else '',
        'campaign_notes':str(getattr(campaign,'extra_text','') or '')[:700] if campaign else '',
        'profile_high_priority':str(getattr(profile,'high_priority_text','') or '')[:1000],
        'profile_medium_priority':str(getattr(profile,'medium_priority_text','') or '')[:700],
        'matched_terms':hits,
        'preference':'Favor small/specialist organizations over large generic employers when the technical relevance and contact reason are similar.',
    }
    prompt=(
        'You are ScoutBox Hidden Lead admission control. Decide whether a website should be admitted as a Hidden Lead. '
        'A Hidden Lead must be a real organization/person/company the user would plausibly want to talk to, track, or contact. '
        'Topical relevance alone is not enough. Require a current practical outreach signal such as consulting/services, contractor/vendor/project demand, partnership, sales inquiry, or active hiring. Reject content-only blogs, directories, generic software pages, job boards, documentation-only pages, marketplaces, SEO/listicles, and pages without a concrete organization identity or reason to contact. '
        'Favor small specialist companies, consultancies, labs, maintainers, security/embedded/Linux/systems shops, niche product vendors, and organizations with a contact path. Large generic companies need a specific team/reason to talk. '
        'Score 0-100 using this rubric: real organization 20, direct relevance 25, practical reason to contact/talk 20, small/specialist bonus 10, contactability 10, multi-page evidence quality 10, noise penalties up to -25. '
        'Return JSON only with keys: decision (admit/review/reject), lead_score (0-100), organization_type, company_name, summary, why_relevant, reason_to_contact, contact_path, small_company_signal (boolean), rejection_risks (array), evidence_urls (array).\n\n'
        'CURRENT LEAD POLICY: '+selectivity_instruction('hidden_leads')+'\n\n'
        'USER/CAMPAIGN SCOPE:\n'+json.dumps(campaign_scope,ensure_ascii=False)+'\n\n'
        'MINIBROWSER EVIDENCE:\n'+str(review.get('text') or '')[:32000]
    )
    model_error=''
    try:
        ai_timeout=max(8,min(45,int(_remaining(45)-2)))
        if ai_timeout < 8:
            raise TimeoutError('Not enough per-lead time remaining for Hidden Lead admission AI call')
        raw=generate(prompt,stage='first_filter',timeout=ai_timeout,subject={'type':'task','id':'hidden-lead-admission','label':f'Hidden Lead gate: {company or url}'})
        row=_hidden_lead_json_object(raw)
    except Exception as exc:
        row={}; model_error=str(exc)[:500]
    def score_value(default=0):
        try: return max(0,min(100,int(row.get('lead_score') if row.get('lead_score') is not None else default)))
        except Exception: return max(0,min(100,int(default or 0)))
    score=score_value(0)
    decision=str(row.get('decision') or '').strip().lower()
    if decision not in {'admit','review','reject'}:
        # Deterministic fallback is intentionally conservative.
        low=(review.get('text') or '').casefold()
        org_terms=sum(1 for m in ('about us','our company','services','solutions','products','contact us','our team','customers','clients') if m in low)
        tech_terms=sum(1 for h in hits if str(h or '').casefold() in low)
        score=max(0,min(74,45+org_terms*5+tech_terms*3))
        decision='review' if score>=_LEAD_MINIBROWSER_REVIEW_CUTOFF else 'reject'
    threshold=int(cutoff or _LEAD_MINIBROWSER_ADMIT_CUTOFF)
    purpose=str(row.get('organization_type') or '').strip().lower().replace(' ','_')
    if purpose in _LEAD_MINIBROWSER_REJECT_PURPOSES and score<threshold+10:
        decision='reject'
    admit=bool(decision=='admit' and score>=threshold)
    out=dict(review)
    out.update({
        'decision':decision,'lead_score':score,'admit':admit,'review':bool(decision=='review' or (not admit and score>=_LEAD_MINIBROWSER_REVIEW_CUTOFF)),
        'cutoff':threshold,'organization_type':str(row.get('organization_type') or '')[:120],
        'company_name':' '.join(str(row.get('company_name') or review.get('company') or company or '').split())[:220],
        'summary':str(row.get('summary') or '')[:1600],'why_relevant':str(row.get('why_relevant') or '')[:1200],
        'reason_to_contact':str(row.get('reason_to_contact') or '')[:1200],'contact_path':str(row.get('contact_path') or review.get('contact_url') or '')[:1000],
        'small_company_signal':bool(row.get('small_company_signal')),
        'rejection_risks':[str(x)[:300] for x in (row.get('rejection_risks') or [])[:8]] if isinstance(row.get('rejection_risks'),list) else [],
        'evidence_urls':[str(x)[:1000] for x in (row.get('evidence_urls') or review.get('pages') or [])[:8]] if isinstance(row.get('evidence_urls') or review.get('pages'),list) else [],
        'model_error':model_error,
        'timeout': bool(review.get('timed_out')) or ('Timeout' in model_error or 'timeout' in model_error.lower()),
        'source':'0.11.11_hidden_lead_minibrowser_admission_bounded',
    })
    return out

def _resolve_editorial_hidden_lead(inspected, terms, *, max_links=3, max_pages=2):
    """Resolve an editorial/publisher article to the real organization it describes."""
    article_text=str((inspected or {}).get('text') or '')[:18000]
    article_domain=registrable_domain((inspected or {}).get('target_url') or '')
    candidates=[]
    for item in (inspected or {}).get('links') or []:
        if not isinstance(item,dict):
            continue
        url=str(item.get('url') or '').strip()
        domain=registrable_domain(url)
        if not url or not domain or domain==article_domain or is_general_market_host(url) or is_job_platform_host(domain):
            continue
        context=(str(item.get('anchor') or '')+' '+str(item.get('context') or '')).casefold()
        score=sum(1 for t in terms if str(t or '').casefold() in context)
        score+=2 if any(x in context for x in ('product','project','company','manufacturer','developer','firmware','hardware')) else 0
        candidates.append((score,url))
    candidates.sort(key=lambda x:x[0],reverse=True)
    for _score,url in candidates[:max(1,int(max_links or 3))]:
        fetched=fetch_target(url,timeout=10)
        if not fetched.get('ok'):
            continue
        final=str(fetched.get('target_url') or url)
        title=str(fetched.get('title') or '')
        text=str(fetched.get('text') or '')[:18000]
        company=display_company_name(company_from_page(final,title,text),final)
        if not is_plausible_company_name(company) or is_general_market_company(company):
            continue
        corr=_corroborate_hidden_lead_organization(final,company,inspected=fetched,initial_title=title,initial_text=text,max_pages=max_pages)
        if not corr.get('verified'):
            continue
        # Require some relation to the originating article to avoid following arbitrary
        # footer/advertising links from a publisher.
        company_tokens=[x for x in re.findall(r'[a-z0-9]+',company.casefold()) if len(x)>=4]
        article_compact=re.sub(r'[^a-z0-9]+',' ',article_text.casefold())
        if company_tokens and not any(tok in article_compact for tok in company_tokens[:4]) and _score<=0:
            continue
        return {'url':final,'company':corr.get('company') or company,'inspected':fetched,'corroboration':corr,'publisher_url':str((inspected or {}).get('target_url') or '')}
    return None


def _salvage_rejection_eligible(reason):
    low=str(reason or '').casefold()
    if not low or any(x in low for x in _SALVAGE_NEGATIVE_MARKERS):
        return False
    return any(x in low for x in _SALVAGE_POSITIVE_MARKERS)


def _opportunity_salvage_evidence(opp):
    intel=getattr(opp,'company_intel',{}) if isinstance(getattr(opp,'company_intel',{}),dict) else {}
    intel_summary=company_summary_from_intel(intel,1200) if intel else ''
    return '\n'.join(str(x or '') for x in (
        getattr(opp,'list_highlight',''),getattr(opp,'recommendation_reason',''),intel_summary,
        getattr(opp,'raw_search_snippet',''),getattr(opp,'description',''),
    ) if str(x or '').strip())[:24000]


def _hidden_market_query_for_market(query, market, rotation_offset=0):
    """Apply configured market geography without adding job-only 'remote' wording."""
    if not market or str(getattr(market,'code','') or '')=='worldwide':
        return ' '.join(str(query or '').split())
    return market_query(query,market,rotation_offset=rotation_offset)


def _translate_hidden_market_query(query, language, protected_term=''):
    """Translate one supplemental Hidden Leads query while preserving the technical term."""
    query=' '.join(str(query or '').split()).strip()
    language=' '.join(str(language or '').split()).strip()[:40]
    if not query or not language:
        return ''
    token='ZXQSBTECHQXZ'
    masked=query
    original=' '.join(str(protected_term or '').split()).strip()
    if original:
        masked=re.sub(re.escape(original),token,masked,count=1,flags=re.I)
    try:
        translated=str(generate(
            f'Translate only the natural-language words in this company/outreach discovery search query into {language}. '
            f'If {token} appears, copy it exactly and do not translate, split, move, or remove it. '
            'Keep the query concise and return only the translated query, no explanation.\n\n'+masked,
            stage='query_planning',timeout=45,
            subject={'type':'task','id':'hidden-market-multilingual','label':f'Hidden Leads query · {language}'},
        ) or '').strip().strip('"')[:300]
    except Exception:
        return ''
    if original:
        match=re.search(re.escape(token),translated,flags=re.I)
        if not match:
            return ''
        translated=translated[:match.start()]+original+translated[match.end():]
    return ' '.join(translated.split()).strip()


def _translate_hidden_market_page(page_text, language, source_url=''):
    """Translate a page only when it came from an explicitly multilingual Hidden Leads query."""
    text=' '.join(str(page_text or '').split())[:16000]
    language=' '.join(str(language or '').split()).strip()[:40]
    if not text or not language:
        return ''
    try:
        translated=str(generate(
            'Translate this organization/company page faithfully into English for lead qualification. '
            'Preserve company names, technical terms, products, services, hiring/project/partner signals, contact details, URLs and uncertainty. '
            'Do not invent a sales need or recommendation. Return only the English interpretation.\n\n'
            f'Language: {language}\nSource: {str(source_url or "")[:1000]}\n\n{text}',
            stage='first_filter',timeout=75,
            subject={'type':'multilingual_source','id':'','label':f'Hidden Lead {language} source interpretation'},
        ) or '').strip()
    except Exception:
        return ''
    if len(translated)<80 or not primarily_english(translated,'en'):
        return ''
    return translated


def _interleave_hidden_query_items(base_items, multilingual_items):
    """Put a small multilingual slice near the front so bounded scans actually execute it."""
    out=[]; extras=list(multilingual_items or []); eidx=0
    for idx,item in enumerate(base_items or []):
        out.append(item)
        if extras and idx % 2 == 1 and eidx < len(extras):
            out.append(extras[eidx]); eidx+=1
    out.extend(extras[eidx:])
    return out


def _salvage_rejected_opportunities(terms, *, max_candidates=24, max_new=6, discovery_mode='source_guided'):
    """Reconsider recently rejected vacancies as company-level Hidden Leads.

    This never resurrects user-deleted Opportunities and never converts a rejection
    automatically.  The company must independently pass technical relevance and
    organization verification.
    """
    cutoff=timezone.now()-timezone.timedelta(days=60)
    qs=Opportunity.objects.filter(user_deleted=False,updated_at__gte=cutoff).filter(Q(status='rejected')|Q(suppressed=True)).exclude(company='').order_by('-updated_at')[:max_candidates]
    created=0; ids=[]; reviewed=0; verified=0; skipped=0
    reasons={'ineligible_reason':0,'weak_signal':0,'weak_outreach_signal':0,'invalid_company':0,'active_opportunity':0,'duplicate':0,'weak_organization':0,'blacklisted':0}
    for opp in qs:
        if created>=max_new:
            break
        reviewed+=1
        reason=str(opp.rejection_reason or '')
        if not _salvage_rejection_eligible(reason):
            reasons['ineligible_reason']+=1; continue
        company=' '.join(str(opp.company or '').split()).strip()
        if not is_plausible_company_name(company) or is_general_market_company(company):
            reasons['invalid_company']+=1; continue
        if active_opportunity_for_company(company,opp.target_url or opp.url):
            reasons['active_opportunity']+=1; continue
        evidence=_opportunity_salvage_evidence(opp)
        blob=evidence.casefold()
        hits=[t for t in terms if str(t or '').casefold() in blob]
        activity=[p for p in ACTIVITY_PHRASES if p in blob]
        if not hits or (not activity and len(hits)<2):
            reasons['weak_signal']+=1; continue
        domain=company_domain_for_entity(opp)
        candidate_url=('https://'+domain+'/' if domain else str(opp.target_url or opp.canonical_url or opp.url or '').strip())
        retained_org=company_info_has_display_data(opp)
        candidate_is_platform=(not candidate_url or is_general_market_host(candidate_url) or is_job_platform_host(registrable_domain(candidate_url)))
        # A company-owned domain is preferred, but not mandatory when ScoutBox already
        # retained credible company research.  Never turn the original job-board URL
        # into the Hidden Lead's company URL in that fallback case.
        if candidate_is_platform and retained_org:
            candidate_url=''
            corr={'verified':True,'company':company,'confidence':76,'reason':'retained_company_research','pages':[],'text':evidence,'contact_url':''}
        elif candidate_is_platform:
            reasons['weak_organization']+=1; continue
        else:
            corr=None
        if candidate_url and is_blacklisted_url(candidate_url,scope='hidden_leads',company=company):
            reasons['blacklisted']+=1; continue
        if recycled_lead_match(company,candidate_url) or active_duplicate_lead(company,candidate_url) or CompanyLead.objects.filter(user_deleted=False,company__iexact=company).exists():
            reasons['duplicate']+=1; continue
        max_pages=3 if str(discovery_mode or '').casefold()=='cloud_web' else 2
        if corr is None:
            corr=_corroborate_hidden_lead_organization(candidate_url,company,initial_title=company,initial_text=evidence,max_pages=max_pages)
        if not corr.get('verified'):
            # Existing company intelligence can corroborate a company without another
            # network success; this is still retained evidence, not a guessed domain.
            if retained_org:
                corr={'verified':True,'company':company,'confidence':76,'reason':'retained_company_research','pages':[],'text':evidence,'contact_url':''}
            else:
                reasons['weak_organization']+=1; continue
        verified+=1
        target=str((corr.get('pages') or ([candidate_url] if candidate_url else []))[0] if (corr.get('pages') or candidate_url) else '')[:1000]
        contactable=bool(getattr(opp,'contact_email','') or corr.get('contact_url'))
        outreach=_hidden_lead_outreach_signal((corr.get('text') or '')+' '+evidence,contactable=contactable,provenance='salvaged_opportunity')
        outreach_min=int(lead_policy(selectivity_current('hidden_leads')).get('outreach_signal_min') or 3)
        if int(outreach.get('score') or 0) < outreach_min:
            reasons['weak_outreach_signal']+=1; continue
        score,components=_hidden_lead_score(company,(corr.get('text') or '')+' '+evidence,hits,activity,organization_confidence=corr.get('confidence'),contactable=contactable,provenance='salvaged_opportunity')
        components['outreach_signal']=outreach
        structural=any(marker in reason.casefold() for marker in ('shipping','equipment','timezone','time zone','onsite','on-site','office presence','location restriction','region restriction','europe only','eu only'))
        if structural:
            score=max(25,score-8)
            components['structural_blocker_penalty']=8
        if selectivity_current('hidden_leads')=='specialist' and (score < 80 or len(set(str(x).casefold() for x in hits if str(x).strip())) < 2):
            reasons['weak_signal']+=1; continue
        summary=company_summary_from_intel(opp.company_intel,1200) or preliminary_company_summary(company,company,evidence,hits)
        context=' '.join(reason.split())[:700]
        lead=CompanyLead.objects.create(
            company=company,source=opp.source,country=opp.country,match_summary=('Retained as company-level lead · Relevant: '+', '.join(hits[:6]))[:2000],
            summary=summary,evidence=evidence,company_intel=(opp.company_intel if isinstance(opp.company_intel,dict) else {}),
            search_url=str(opp.target_url or opp.url or '')[:1000],target_url=target,source_url=target,
            contact_email=(clean_contact_email(opp.contact_email) if assignable_contact_email(opp.contact_email,evidence) else ''),
            contact_name=str(opp.contact_name or '')[:200],contact_url=str(corr.get('contact_url') or '')[:1000],score=score,status='review',
            note='',
        )
        state=dict(lead.ai_state or {})
        state['provenance']={'type':'salvaged_opportunity','opportunity_id':opp.pk,'opportunity_title':opp.title[:300],'rejection_reason':context,'at':timezone.now().isoformat()}
        state['hidden_lead_score']=components
        state['organization_corroboration']={k:v for k,v in corr.items() if k not in {'text'}}
        lead.ai_state=state; lead.save(update_fields=['ai_state','updated_at'])
        try:
            for campaign in opp.campaigns.filter(deleted_at__isnull=True):
                lead.campaigns.add(campaign)
            if opp.origin_campaign_id:
                lead.origin_campaign=opp.origin_campaign; lead.save(update_fields=['origin_campaign','updated_at'])
        except Exception:
            pass
        try:
            promote_record_contact_to_addressbook(lead,source='Salvaged Opportunity Hidden Lead',source_url=target,texts=(evidence,),confidence=max(70,score),queue_research=False)
        except Exception:
            pass
        ids.append(lead.pk); created+=1
    return {'reviewed':reviewed,'verified':verified,'created':created,'lead_ids':ids,'rejections':reasons}

def scan_hidden_market(max_queries=48, progress_callback=None, max_seconds=2400):
    """Find technically relevant organizations even when no suitable role is advertised.

    0.10.93 deliberately separates technical-interest evidence from organization
    verification.  A project/blog/case-study page may discover the company; a small,
    bounded same-domain corroboration pass proves that the organization is real.
    Recently rejected Opportunities are also reconsidered at company level when the
    vacancy failed for a salvageable reason.
    """
    terms=_terms()
    settings_row=PortalSettings.objects.get_or_create(pk=1)[0]
    discovery_mode=str(settings_row.discovery_mode or 'source_guided').strip().lower()
    lead_level=selectivity_current('hidden_leads',settings_row); lead_rules=lead_policy(lead_level)
    # Balanced/Specialist Hidden Leads search for evidence of a practical company/outreach
    # relationship instead of filling the budget with generic technical mentions. Broad
    # keeps two activity-oriented probes for adjacent organizations.
    commercial_patterns=[
        '"{term}" "engineering services"', '"{term}" consulting', '"{term}" "custom engineering"',
        '"{term}" "contact sales"', '"{term}" contractor', '"{term}" "technology partner"',
        '"{term}" "professional services"', '"{term}" "partner with us"',
    ]
    activity_patterns=['"{term}" "we built"','"{term}" "case study"','"{term}" project','"{term}" "working on"']
    patterns=(commercial_patterns+activity_patterns) if lead_level=='broad' else (commercial_patterns+activity_patterns[:2] if lead_level=='balanced' else commercial_patterns)
    # Rotate the term window every normal Hidden Leads cadence. The same rotation also
    # drives market/language selection so Balanced market coverage moves over time.
    if terms:
        try:
            bucket=int(timezone.now().timestamp()//1800)
            offset=bucket % len(terms)
        except Exception:
            offset=0
        rotated_terms=terms[offset:]+terms[:offset]
    else:
        offset=0; rotated_terms=[]
    coverage=market_plan(settings_row,campaign_id=0,rotation_offset=offset)
    markets=list(coverage.get('markets') or [])
    multilingual_plan=multilingual_assignments(settings_row,markets,rotation_offset=offset)
    # Balanced currently means at most two multilingual supplemental searches. Reserve
    # those slots instead of growing the configured scan budget invisibly.
    base_query_cap=max(1,int(max_queries or 48)-len(multilingual_plan))
    base_queries=[]; base_terms=[]
    for pass_index in range(len(patterns)):
        for term_index,term in enumerate(rotated_terms):
            pattern=patterns[(pass_index+term_index+offset) % len(patterns)]
            q=pattern.format(term=term)
            if q not in base_queries:
                base_queries.append(q); base_terms.append(term)
            if len(base_queries)>=base_query_cap:
                break
        if len(base_queries)>=base_query_cap:
            break
    scheduled_markets=market_workload_schedule(coverage,len(base_queries),rotation_offset=offset)
    base_items=[]
    for idx,q in enumerate(base_queries):
        market=scheduled_markets[idx] if idx<len(scheduled_markets) else (markets[idx%len(markets)] if markets else None)
        base_items.append({'query':_hidden_market_query_for_market(q,market,rotation_offset=offset+idx),
                           'base_query':q,'term':base_terms[idx] if idx<len(base_terms) else '',
                           'market_obj':market,'market':market_search_meta(market),'multilingual_language':'','multilingual_id':''})
    multilingual_items=[]
    for idx,assignment in enumerate(multilingual_plan):
        if not base_queries: break
        source_idx=idx % len(base_queries); source_q=base_queries[source_idx]; protected_term=base_terms[source_idx] if source_idx<len(base_terms) else ''
        translated=_translate_hidden_market_query(source_q,assignment.get('language'),protected_term)
        if not translated: continue
        market=assignment.get('market')
        multilingual_items.append({'query':_hidden_market_query_for_market(translated,market,rotation_offset=offset+idx),
                                    'base_query':source_q,'term':protected_term,'market_obj':market,
                                    'market':market_search_meta(market),'multilingual_language':assignment.get('language',''),
                                    'multilingual_id':assignment.get('id',''),'multilingual_source':assignment.get('source','')})
    query_items=_interleave_hidden_query_items(base_items,multilingual_items)[:max(1,int(max_queries or 48))]
    queries=[item.get('query','') for item in query_items]
    providers=_providers(limit=4); created=0; results_seen=0; errors=[]; lead_ids=[]; changed_lead_ids=[]
    local_language_gate=(discovery_mode=='source_guided')
    corroboration_pages=(3 if discovery_mode=='cloud_web' else 2)
    started=time.monotonic(); deadline=started+max(300,int(max_seconds or 2400)); budget_reached=False
    base_queries_per_provider=min(6,len(base_items)); total_units=max(1,len(providers)*max(1,base_queries_per_provider+len(multilingual_items))); completed_units=0
    automatic_new_cap=max(1,int(lead_rules.get('automatic_scan_new_cap') or 7))
    try:
        provider_error_limit=max(1,min(8,int(os.environ.get('SCOUTBOX_SEARCH_PROVIDER_MAX_CONSECUTIVE_ERRORS','2') or 2)))
    except Exception:
        provider_error_limit=2
    def report(message):
        if progress_callback:
            try: progress_callback(completed_units,total_units,message)
            except Exception: pass
    filtered={
        'job_like':0,'weak_signal':0,'weak_outreach_signal':0,'weak_organization':0,'duplicate':0,'blacklisted':0,
        'fetch_failed':0,'general_platform':0,'documentation':0,'publisher_or_forum':0,
        'non_english':0,'adult_content':0,'represented_by_opportunity':0,'invalid_company':0,
        'corroboration_budget_exhausted':0,'new_lead_cap_reached':0,
    }
    # Same-domain corroboration is deliberately bounded across the whole scan so Hidden
    # Leads cannot turn a broad search pass into uncontrolled crawling. Cloud mode gets a
    # slightly larger allowance because it is already an explicitly deeper discovery mode.
    corroboration_cap=(16 if discovery_mode=='cloud_web' else 12)
    corroborations_used=0
    funnel={
        'fetched':0,'technically_relevant':0,'needs_corroboration':0,'organization_verified':0,
        'publisher_resolved':0,'accepted':0,'already_represented_by_opportunity':0,
        'corroboration_cap':corroboration_cap,
    }
    provider_summary=[]
    for provider in providers:
        pseen=0; pnew=0; perr=[]; consecutive_errors=0; pmultilingual=0
        provider_queries=min(base_queries_per_provider,provider_query_allowance(provider,base_queries_per_provider))
        provider_base=[item for item in query_items if not item.get('multilingual_id')]
        provider_multi=[item for item in query_items if item.get('multilingual_id')]
        item_offset=((provider.pk or 0)*5) % max(1,len(provider_base))
        selected_base=(provider_base[item_offset:]+provider_base[:item_offset])[:provider_queries] if provider_base else []
        # Multilingual work is intentionally tiny (Low/Balanced/High cap from Search
        # Settings), and is supplemental to the provider's adaptive English allowance.
        selected_multi=[item for item in provider_multi if provider_market_compatible(provider,item.get('market_obj'))]
        pqueries=_interleave_hidden_query_items(selected_base,selected_multi)
        for query_index,query_item in enumerate(pqueries,1):
            query=str(query_item.get('query') or '')
            market=query_item.get('market_obj'); market_info=query_item.get('market') or {}
            if not query or not provider_market_compatible(provider,market):
                continue
            if time.monotonic()>=deadline:
                budget_reached=True; break
            report(f'Scanning {provider.name} · query {query_index}/{len(pqueries)}')
            rows,err=search_source(provider,query,limit=6,usage_category='hidden_market',market=market,query_language=(query_item.get('multilingual_language') or 'English'))
            if query_item.get('multilingual_id'):
                pmultilingual+=1
            if market_info.get('market_code'):
                UsageMetric.objects.create(category='discovery_market',provider=provider.name,stage='query',requests=1,pages=len(rows or []),errors=1 if err else 0,
                    metadata={'market_code':market_info.get('market_code'),'market':market_info.get('market',''),'multilingual_language':query_item.get('multilingual_language',''),'multilingual':bool(query_item.get('multilingual_id')),'source':'hidden_market'})
            if err:
                consecutive_errors+=1
                perr.append(err); errors.append(f'{provider.name}: {err}'); completed_units+=1; report(f'Scanning {provider.name} · query {query_index}/{len(pqueries)}')
                if consecutive_errors>=provider_error_limit:
                    errors.append(f'{provider.name}: Hidden Leads scan stopped this provider after {consecutive_errors} consecutive request errors; remaining queries will rotate into a later scan.')
                    break
                continue
            consecutive_errors=0
            results_seen+=len(rows); pseen+=len(rows)
            for row in rows:
                if time.monotonic()>=deadline:
                    budget_reached=True; break
                search_url=unwrap_search_result_url((row.get('url') or '').strip())
                if is_disallowed_adult_url(search_url): filtered['adult_content']+=1; continue
                if is_blacklisted_url(search_url, scope='hidden_leads'): filtered['blacklisted']+=1; continue
                # Editorial pages may be useful discovery evidence for a company, but job
                # boards/search/social/community hosts are never Hidden Lead companies.
                search_general=is_general_market_host(search_url)
                if search_general and not _is_editorial_discovery_host(search_url):
                    filtered['general_platform']+=1; continue
                title=(row.get('title') or '').strip(); snippet=(row.get('snippet') or '').strip()
                inspected=fetch_target(search_url,title,snippet,timeout=12)
                target=unwrap_search_result_url((inspected.get('target_url') or search_url).strip())
                if is_search_engine_url(target): filtered['general_platform']+=1; continue
                if is_disallowed_adult_url(target): filtered['adult_content']+=1; continue
                if is_blacklisted_url(target, scope='hidden_leads'): filtered['blacklisted']+=1; continue
                if is_search_engine_url(search_url): search_url=target
                target_general=is_general_market_host(target)
                if target_general and not _is_editorial_discovery_host(target): filtered['general_platform']+=1; continue
                if not inspected.get('ok'): filtered['fetch_failed']+=1; continue
                funnel['fetched']+=1
                evidence=(inspected.get('text') or '').strip()[:18000]
                page_title=(inspected.get('title') or title).strip()
                translation_applied=False
                if local_language_gate and not primarily_english(evidence, inspected.get('language_code') or ''):
                    planned_language=str(query_item.get('multilingual_language') or '').strip()
                    if planned_language:
                        translated=_translate_hidden_market_page(evidence,planned_language,target)
                        if translated:
                            evidence=translated[:18000]; translation_applied=True
                        else:
                            filtered['non_english']+=1; continue
                    else:
                        filtered['non_english']+=1; continue
                if is_documentation_like(target,page_title,evidence) and not _is_editorial_discovery_host(target):
                    filtered['documentation']+=1; continue

                publisher_url=''
                preverified=None
                # Resolve a publication such as Hackaday to the actual organization it
                # discusses. The publisher itself is never persisted as the company.
                if _is_editorial_discovery_host(target):
                    resolved=_resolve_editorial_hidden_lead(inspected,terms,max_links=3,max_pages=corroboration_pages)
                    if not resolved:
                        filtered['publisher_or_forum']+=1; continue
                    publisher_url=target
                    target=resolved['url']; inspected=resolved['inspected']; preverified=resolved['corroboration']
                    evidence=(inspected.get('text') or '').strip()[:18000]
                    page_title=(inspected.get('title') or page_title).strip()
                    if local_language_gate and not primarily_english(evidence, inspected.get('language_code') or ''):
                        planned_language=str(query_item.get('multilingual_language') or '').strip()
                        translated=_translate_hidden_market_page(evidence,planned_language,target) if planned_language else ''
                        if not translated:
                            filtered['non_english']+=1; continue
                        evidence=translated[:18000]; translation_applied=True
                    funnel['publisher_resolved']+=1

                blob=(page_title+' '+evidence).lower()
                # Hidden Leads are not a second jobs feed. Job pages can still reach this
                # system later through the rejected-Opportunity salvage path.
                if _hidden_page_is_job_like(target,page_title,evidence): filtered['job_like']+=1; continue
                hits=[t for t in terms if str(t or '').lower() in blob]
                activity=[p for p in ACTIVITY_PHRASES if p in blob]
                if not hits or (not activity and len(hits)<2):
                    filtered['weak_signal']+=1; continue
                funnel['technically_relevant']+=1
                domain=source_domain(target)
                if not domain: filtered['weak_signal']+=1; continue
                company=(preverified or {}).get('company') or company_from_page(target,page_title,evidence)
                company=display_company_name(company,target)
                if not is_plausible_company_name(company) or is_general_market_company(company):
                    filtered['invalid_company']+=1; continue
                if is_blacklisted_url(target, scope='hidden_leads', company=company): filtered['blacklisted']+=1; continue

                corr=preverified
                if not corr or not corr.get('verified'):
                    path=(urllib.parse.urlparse(target).path or '').casefold()
                    personalish=any(x in path for x in ('/blog/','/posts/','/author/','/archives/')) and not any(x in blob for x in ('our products','our services','we build','we develop','we design','contact sales','our customers','our clients'))
                    page_org=(not personalish) and _hidden_lead_organization_signal(company,blob,technical_hits=len(hits),activity_hits=len(activity))
                    if page_org:
                        corr={'verified':True,'company':company,'confidence':80,'reason':'first_party_discovery_page','pages':[target],'text':page_title+' '+evidence,'contact_url':''}
                    else:
                        funnel['needs_corroboration']+=1
                        corr=_retained_company_corroboration(company,target)
                        if corr is None:
                            if corroborations_used>=corroboration_cap:
                                filtered['corroboration_budget_exhausted']+=1
                                continue
                            corroborations_used+=1
                            corr=_corroborate_hidden_lead_organization(
                                target,company,inspected=inspected,initial_title=page_title,initial_text=evidence,
                                max_pages=corroboration_pages,
                            )
                if not corr.get('verified'):
                    filtered['weak_organization']+=1; continue
                funnel['organization_verified']+=1
                company=display_company_name(corr.get('company') or company,target)
                target_pages=corr.get('pages') or []
                company_target=str(target_pages[0] if target_pages else target)[:1000]
                if active_opportunity_for_company(company,company_target):
                    filtered['represented_by_opportunity']+=1; funnel['already_represented_by_opportunity']+=1; continue
                if recycled_lead_match(company,company_target):
                    filtered['duplicate']+=1; continue
                if adult_content_reason(page_title,evidence,target): filtered['adult_content']+=1; continue

                contactable=bool(corr.get('contact_url') or re.search(_THIRD_PARTY_EMAIL_RE,evidence))
                outreach=_hidden_lead_outreach_signal((corr.get('text') or '')+' '+blob,contactable=contactable,provenance='discovered_company')
                if int(outreach.get('score') or 0) < int(lead_rules.get('outreach_signal_min') or 3):
                    filtered['weak_outreach_signal']+=1
                    continue
                score,score_parts=_hidden_lead_score(
                    company,(corr.get('text') or '')+' '+blob,hits,activity,
                    organization_confidence=corr.get('confidence'),contactable=contactable,
                    provenance='discovered_company',
                )
                score_parts['outreach_signal']=outreach
                lang=(inspected.get('language_code') or '')[:16]
                if lang and lang!='en' and not translation_applied: score=max(0,score-6)
                if inspected.get('is_pdf'): score=max(0,score-15)
                if lead_level=='specialist' and (score < 80 or len(set(str(x).casefold() for x in hits if str(x).strip())) < 2):
                    filtered['weak_signal']+=1
                    continue
                summary=preliminary_company_summary(company,page_title,evidence,hits)
                _status=inspected.get('http_status')
                try: _status=int(_status) if _status is not None else None
                except Exception: _status=None
                defaults={
                    'company':company,'country':infer_country(company_target,(corr.get('text') or '')+' '+page_title+' '+evidence),
                    'match_summary':', '.join(hits[:6]),'summary':summary,'evidence':evidence,'score':score,'status':'review',
                    'search_url':publisher_url or search_url,'target_url':company_target,'source_url':company_target,'language_code':lang,'source':provider,
                    'contact_url':str(corr.get('contact_url') or '')[:1000],
                    'target_http_status':_status,'target_checked_at':(timezone.now() if _status is not None or inspected.get('error') else None),
                    'target_check_error':str(inspected.get('error') or '')[:500],
                }
                lead=active_duplicate_lead(company,company_target) or CompanyLead.objects.filter(user_deleted=False,company__iexact=company).order_by('-score','-created_at').first()
                if not lead and created>=automatic_new_cap:
                    filtered['new_lead_cap_reached']+=1
                    continue
                materially_changed=False
                if lead:
                    update_fields=[]
                    if score >= int(lead.score or 0):
                        before='\n'.join(str(getattr(lead,k,'') or '') for k in ('company','country','match_summary','evidence','target_url','source_url'))
                        after='\n'.join(str(defaults.get(k,'') or '') for k in ('company','country','match_summary','evidence','target_url','source_url'))
                        materially_changed=hashlib.sha256(before.encode('utf-8','ignore')).hexdigest()!=hashlib.sha256(after.encode('utf-8','ignore')).hexdigest()
                        for key,value in defaults.items(): setattr(lead,key,value)
                        update_fields.extend(defaults.keys())
                    else:
                        lead.target_http_status=_status
                        lead.target_checked_at=(timezone.now() if _status is not None or inspected.get('error') else lead.target_checked_at)
                        lead.target_check_error=str(inspected.get('error') or '')[:500]
                        update_fields.extend(['target_http_status','target_checked_at','target_check_error'])
                        if not lead.target_url: lead.target_url=company_target; update_fields.append('target_url')
                        if not lead.source_url: lead.source_url=company_target; update_fields.append('source_url')
                    state=dict(lead.ai_state or {})
                    state['provenance']={'type':'discovered_company','publisher_url':publisher_url,'discovery_url':search_url,'market_code':str((query_item.get('market') or {}).get('market_code') or ''),'market':str((query_item.get('market') or {}).get('market') or ''),'multilingual_language':str(query_item.get('multilingual_language') or ''),'translation_applied':bool(translation_applied),'at':timezone.now().isoformat()}
                    state['hidden_lead_score']=score_parts
                    state['organization_corroboration']={k:v for k,v in corr.items() if k!='text'}
                    lead.ai_state=state; update_fields.append('ai_state')
                    if update_fields: lead.save(update_fields=list(dict.fromkeys(update_fields+['updated_at'])))
                    was_new=False
                else:
                    lead=CompanyLead.objects.create(**defaults)
                    state=dict(lead.ai_state or {})
                    state['provenance']={'type':'discovered_company','publisher_url':publisher_url,'discovery_url':search_url,'market_code':str((query_item.get('market') or {}).get('market_code') or ''),'market':str((query_item.get('market') or {}).get('market') or ''),'multilingual_language':str(query_item.get('multilingual_language') or ''),'translation_applied':bool(translation_applied),'at':timezone.now().isoformat()}
                    state['hidden_lead_score']=score_parts
                    state['organization_corroboration']={k:v for k,v in corr.items() if k!='text'}
                    lead.ai_state=state; lead.save(update_fields=['ai_state','updated_at'])
                    was_new=True; materially_changed=True
                try:
                    promote_record_contact_to_addressbook(
                        lead,source=f'Source-guided Hidden Lead · {provider.name}',source_url=company_target,
                        texts=(evidence,page_title),confidence=max(70,score),queue_research=False,
                    )
                except Exception:
                    pass
                if lead.pk not in lead_ids: lead_ids.append(lead.pk)
                if materially_changed and lead.pk not in changed_lead_ids: changed_lead_ids.append(lead.pk)
                if was_new: created+=1; pnew+=1; funnel['accepted']+=1
                else: filtered['duplicate']+=1
            completed_units+=1; report(f'Scanning {provider.name} · query {query_index}/{len(pqueries)}')
            if budget_reached: break
        provider_summary.append({'provider':provider.name,'results':pseen,'new':pnew,'multilingual_queries':pmultilingual,'errors':perr[:3]})
        if budget_reached: break

    # Reconsider unsuitable/dead vacancies as company-level leads.  This is a bounded
    # second input stream and never touches user-deleted Opportunities.
    salvage={'reviewed':0,'verified':0,'created':0,'lead_ids':[],'rejections':{}}
    salvage_remaining=max(0,automatic_new_cap-created)
    if salvage_remaining and not budget_reached and time.monotonic()<deadline:
        try:
            salvage=_salvage_rejected_opportunities(terms,max_candidates=48,max_new=min(6,salvage_remaining),discovery_mode=discovery_mode)
            created+=int(salvage.get('created') or 0)
            for lead_id in salvage.get('lead_ids') or []:
                if lead_id not in lead_ids: lead_ids.append(lead_id)
                if lead_id not in changed_lead_ids: changed_lead_ids.append(lead_id)
        except Exception as exc:
            errors.append('Opportunity salvage: '+str(exc)[:500])

    ps=PortalSettings.objects.get_or_create(pk=1)[0]; ps.last_hidden_scan=timezone.now(); ps.save(update_fields=['last_hidden_scan','updated_at'])
    elapsed_seconds=int(time.monotonic()-started)
    funnel['corroborations_used']=corroborations_used
    return {
        'providers':[p.name for p in providers],'provider_summary':provider_summary,'queries':queries,
        'results_seen':results_seen,'new_leads':created,'lead_ids':lead_ids,'changed_lead_ids':changed_lead_ids,
        'filtered':filtered,'funnel':funnel,'opportunity_salvage':salvage,'errors':errors[:30],
        'lead_selectivity':lead_level,'automatic_new_cap':automatic_new_cap,
        'market_strategy':str(getattr(settings_row,'discovery_market_strategy','balanced') or 'balanced'),
        'market_plan':list(coverage.get('ordered_codes') or []),
        'multilingual_strength':str(getattr(settings_row,'multilingual_exploration_strength','balanced') or 'balanced'),
        'multilingual_planned':[{'language':x.get('language',''),'market':getattr(x.get('market'),'name',''),'source':x.get('source','')} for x in multilingual_plan],
        'multilingual_executed':sum(int(x.get('multilingual_queries') or 0) for x in provider_summary),
        'partial':budget_reached,'time_budget_reached':budget_reached,'elapsed_seconds':elapsed_seconds,
    }


def _outreach_subject_fallback(lead, profile=None):
    """Build a specific immediate subject so queued outreach never appears as 'Direct outreach'."""
    profile=profile or Profile.objects.get_or_create(pk=1)[0]
    evidence=' '.join(str(x or '') for x in (lead.summary,lead.match_summary,lead.evidence))
    offerings=_named_offerings(evidence)
    topics=_summary_topics(evidence)
    try:
        search_profile=build_search_profile()
        profile_terms=[str(x.get('term') or '').strip() for x in (search_profile.get('skills') or []) if str(x.get('term') or '').strip()]
    except Exception:
        profile_terms=[]
    low=evidence.lower()
    matched=[]
    for term in profile_terms:
        t=term.lower()
        if t and t in low and t not in {x.lower() for x in matched}:
            matched.append(term)
        if len(matched)>=3: break
    focus=''
    if offerings:
        focus=offerings[0]
    elif topics:
        focus=topics[0]
    elif matched:
        focus=matched[0]
    else:
        focus='embedded systems'
    action_map={
        'GPU computing':'GPU engineering', 'AI systems':'AI systems', 'virtualization':'virtualization engineering',
        'emulation':'emulation engineering', 'firmware':'firmware engineering', 'device drivers':'driver engineering',
        'embedded systems':'embedded engineering', 'reverse engineering':'reverse-engineering support',
        'binary analysis':'binary-analysis support', 'protocols':'protocol integration', 'legacy systems':'legacy systems engineering',
        'hardware bring-up':'hardware bring-up',
    }
    action=action_map.get(focus, action_map.get(topics[0] if topics else '', 'technical collaboration'))
    # Named products/projects make stronger subjects than generic technology labels.
    if offerings:
        subject=f'{offerings[0]} — {action}'
    else:
        subject=f'{action} for {lead.company}'
    words=subject.split()
    if len(words)>9:
        subject=' '.join(words[:9])
    return subject.strip(' -—:')[:500]

def ensure_outreach_application(lead):
    """Create/update the unified Applications & Outreach record for a Hidden Leads outreach draft."""
    facts_key={'market_study_lead_id':lead.pk,'outreach':True}
    current_subject=(lead.draft_subject or '').strip()
    low_subject=re.sub(r'[^a-z0-9 ]+',' ',current_subject.lower()).strip()
    if not current_subject or low_subject in {'direct outreach','specialist support','opportunity','hello','direct outreach email'} or low_subject.startswith('direct outreach'):
        lead.draft_subject=_outreach_subject_fallback(lead)
        lead.save(update_fields=['draft_subject','updated_at'])
    opp=None
    for candidate in Opportunity.objects.filter(company__iexact=lead.company).order_by('-updated_at')[:50]:
        facts=candidate.extracted_facts or {}
        if facts.get('market_study_lead_id')==lead.pk and facts.get('outreach') is True:
            if candidate.user_deleted:
                raise RuntimeError('The related outreach opportunity is in the Recycle Bin. Restore it before preparing outreach again.')
            opp=candidate; break
    target=(lead.target_url or lead.source_url or f'https://manual.invalid/market-outreach-{lead.pk}').strip()
    description='\n\n'.join(x for x in [lead.summary, lead.match_summary, lead.evidence] if str(x or '').strip())[:30000]
    if opp is None:
        opp=Opportunity.objects.create(
            title=(lead.draft_subject or _outreach_subject_fallback(lead))[:300],company=lead.company,country=lead.country,url=target,
            canonical_url=(target if target.startswith(('http://','https://')) and 'manual.invalid' not in target else ''),
            target_url=(target if target.startswith(('http://','https://')) and 'manual.invalid' not in target else ''),
            search_url=lead.search_url,channel='email',contact_email=lead.contact_email,contact_name=lead.contact_name,
            description=description,status='draft',fit_score=lead.score,is_read=True,suppressed=True,
            application_draft_requested_at=timezone.now(),extracted_facts=facts_key,
        )
    else:
        opp.title=(lead.draft_subject or _outreach_subject_fallback(lead))[:300]
        opp.company=lead.company; opp.country=lead.country; opp.channel='email'; opp.contact_email=lead.contact_email; opp.contact_name=lead.contact_name
        opp.description=description; opp.fit_score=lead.score; opp.search_url=lead.search_url or opp.search_url; opp.suppressed=True
        if target and 'manual.invalid' not in target:
            opp.url=target; opp.canonical_url=target; opp.target_url=target
        facts=dict(opp.extracted_facts or {}); facts.update(facts_key); opp.extracted_facts=facts
        opp.save()
    copy_lead_campaigns_to_opportunity(lead,opp)
    app,_=Application.objects.get_or_create(opportunity=opp)
    if app.deleted_at:
        raise RuntimeError('The related application/outreach record is in the Recycle Bin. Restore it before preparing outreach again.')
    app.email_subject=lead.draft_subject; app.email_body=lead.draft_body; app.email_mode='plain'; app.is_read=False
    if app.status not in ('applied','reply','interview','rejected','accepted','closed'):
        app.status='prepared'
    if not app.notes:
        app.notes=f'Outreach prepared from Hidden Leads lead #{lead.pk}.'
    app.save()
    return app


def generate_cold_draft(lead,provider=None,model=None):
    profile=Profile.objects.get_or_create(pk=1)[0]
    prompt=f'''Prepare a short, non-pushy cold-contact email based only on the supplied evidence. Do not claim there is an open job. The evidence may simply show interesting technical work; frame the message as an offer of relevant specialist help. Do not invent experience.
Create a specific email subject of roughly 4-9 words that reflects the strongest relevant product, project, or technical area and the nature of the outreach. It may mention a concrete technology such as GPU, AI, firmware, QEMU, embedded Linux, reverse engineering, drivers, emulation, or another evidenced area when genuinely relevant. Do not use generic subjects such as "Direct outreach", "Specialist support", "Opportunity", or "Hello".
Candidate HIGH priorities: {profile.high_priority_text}
Candidate MEDIUM priorities: {profile.medium_priority_text}
Candidate LOW priorities: {profile.low_priority_text}
Portfolio: {profile.portfolio_url}
Company: {lead.company}
Company summary: {lead.summary}
Evidence: {lead.evidence[:6500]}
Match: {lead.match_summary}
Return plain text beginning with Subject: ...'''
    try:
        text=generate(prompt,stage='email_draft',provider=provider,model=model,subject={'type':'hidden lead','id':lead.pk,'label':lead.company})
    except Exception:
        text=''
    lines=(text or '').strip().splitlines()
    if lines and lines[0].lower().startswith('subject:'):
        lead.draft_subject=lines[0].split(':',1)[1].strip()[:500]; lead.draft_body='\n'.join(lines[1:]).strip()
    elif text:
        topics=_summary_topics(' '.join([lead.summary or '',lead.match_summary or '',lead.evidence or '']))
        focus=(topics[0] if topics else 'engineering').title()
        lead.draft_subject=f'{focus} collaboration with {lead.company}'[:500]; lead.draft_body=(text or '').strip()
    else:
        topics=_summary_topics(' '.join([lead.summary or '',lead.match_summary or '',lead.evidence or '']))
        focus=(topics[0] if topics else 'engineering').title()
        lead.draft_subject=f'{focus} collaboration with {lead.company}'[:500]
        focus=(lead.summary or lead.match_summary or 'your technical work').strip()
        lead.draft_body=(f"Hello,\n\nI came across {lead.company} while researching organizations working in areas close to my embedded and low-level software background. "
                         f"{focus[:700]}\n\nIf useful, I would be happy to discuss whether I could help with a relevant engineering or compatibility problem. "
                         f"Portfolio: {profile.portfolio_url}\n\nRegards,\n{profile.display_name}").strip()
    generic_subjects={'direct outreach','specialist support','opportunity','hello','engineering collaboration','direct outreach email'}
    low_subject=re.sub(r'[^a-z0-9 ]+',' ',(lead.draft_subject or '').strip().lower()).strip()
    if low_subject in generic_subjects or low_subject.startswith('direct outreach') or len((lead.draft_subject or '').split())<3:
        lead.draft_subject=_outreach_subject_fallback(lead,profile)
    if profile.display_name:
        lead.draft_body=re.sub(r'\[\s*your\s+name\s*\]',profile.display_name,lead.draft_body or '',flags=re.I)
        lead.draft_body=re.sub(r'\{\{\s*your(?:\s+|_)name\s*\}\}',profile.display_name,lead.draft_body or '',flags=re.I)
        lead.draft_body=re.sub(r'\[\s*name\s*\]',profile.display_name,lead.draft_body or '',flags=re.I)
        lead.draft_body=re.sub(r'\[\s*'+re.escape(profile.display_name)+r'\s*\]',profile.display_name,lead.draft_body or '',flags=re.I)
    lead.draft_body=re.sub(r'(?im)^\s*\[\s*your\s+position\s*\]\s*$', '', lead.draft_body or '')
    contact=(profile.phone_number or profile.application_email or '').strip()
    lead.draft_body=re.sub(r'\[\s*your\s+contact\s+information\s*\]',contact,lead.draft_body or '',flags=re.I)
    lead.draft_body=re.sub(r'\n{3,}','\n\n',lead.draft_body or '').strip()
    lead.save(update_fields=['draft_subject','draft_body','updated_at'])
    return ensure_outreach_application(lead)

