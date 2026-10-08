import json
import ast
import re
import urllib.parse
from django.utils.safestring import mark_safe
from django.utils.html import escape, strip_tags
from portal.services.presentation import clean_placeholder, rich_html, human_facts, confidence_band, simple_job_html
from portal.services.cold import display_company_name, hidden_lead_summary_is_generic, hidden_lead_summary_has_evidence_markers, strip_hidden_lead_evidence_markers
from portal.services.company_research import company_summary_from_intel
from portal.services.platforms import is_plausible_company_name
from portal.services.highlights import derive_opportunity_highlight, normalize_ai_fit_summary, opportunity_specific_highlight, is_specific_highlight, concise_technical_summary
from portal.services.content_quality import sanitize_mixed_script_title, normalize_opportunity_title
from portal.services.provenance import fit_assessment_origin
from portal.services.blacklist import company_specific_blacklist_review_domain as _blacklist_review_domain, company_specific_blacklist_review_domain_for_record as _blacklist_review_domain_for_record, company_blacklist_candidate as _company_blacklist_candidate, clean_blacklist_reason
from portal.services.freshness import opportunity_post_age_sort_days, opportunity_post_age_display_label as _freshness_post_age_display_label
from portal.services.tracking import clean_article_title, article_title_needs_refresh
from portal.services.location_values import location_labels, location_icon, record_location_display as _record_location_display, record_location_items as _record_location_items, record_location_title as _record_location_title, location_display_text
from portal.ui import COUNTRIES
from django import template
register=template.Library()

@register.filter
def tracking_article_title(value):
    """Never render a stored URL/Markdown placeholder as if it were the page title."""
    if article_title_needs_refresh(value):
        return ''
    return clean_article_title(value)

@register.simple_tag
def tracking_article_display(rule):
    """Return a real stored page title, never a legacy slug/rule-name placeholder."""
    if not rule:
        return ''
    value=getattr(rule,'article_title','')
    if article_title_needs_refresh(value,getattr(rule,'destination_url',''),getattr(rule,'name',''),getattr(rule,'base_path','')):
        return ''
    return clean_article_title(value)

@register.filter
def normalize_evidence_ellipsis(value):
    """Collapse provider truncation artifacts for display without mutating stored evidence."""
    text=' '.join(str(value or '').split()).strip()
    if not text:
        return ''
    # Search providers often return "snippet... - source ...". Keep one useful visual
    # truncation marker rather than displaying a chain of unrelated literal dot runs.
    text=re.sub(r'\.{3,}\s*[-–—]\s*', ' — ', text)
    text=re.sub(r'\.{3,}', '…', text)
    text=re.sub(r'(?:\s*…\s*){2,}', ' … ', text)
    return ' '.join(text.split())

@register.filter
def compact_external_url(value):
    """Display a URL without its scheme or cosmetic www prefix."""
    text=str(value or '').strip()
    if not text:
        return ''
    try:
        parsed=urllib.parse.urlsplit(text if '://' in text else 'https://'+text)
        host=(parsed.netloc or '').removeprefix('www.')
        path=parsed.path or ''
        query=('?'+parsed.query) if parsed.query else ''
        fragment=('#'+parsed.fragment) if parsed.fragment else ''
        return host+path+query+fragment
    except Exception:
        return re.sub(r'^https?://(?:www\.)?','',text,flags=re.I)

@register.filter
def clean_hidden_lead_reason(value):
    """Remove redundant UI wording from Hidden Lead blacklist explanations."""
    return clean_blacklist_reason(value)
@register.filter
def labelize(value):
    return str(value or '').replace('_',' ').replace('-',' ').strip().title()
@register.filter
def to_json(value):
    try: return json.dumps(value or {}, indent=2, ensure_ascii=False)
    except Exception: return '{}'
@register.filter
def human_bytes(value):
    try: n=float(value or 0)
    except Exception: n=0
    units=['B','KB','MB','GB','TB']
    for unit in units:
        if n<1024 or unit==units[-1]: return f'{n:.1f} {unit}' if unit!='B' else f'{int(n)} B'
        n/=1024

@register.filter
def latency_human(value):
    try:
        n=float(value or 0)
    except Exception:
        n=0.0
    if n > 1000:
        return f'{n/1000.0:.1f} sec'
    return f'{int(round(n))} ms'

@register.filter
def mb_value(value):
    try:
        return f'{float(value or 0)/(1024*1024):.1f}'
    except Exception:
        return '0.0'


@register.filter
def human_mb(value):
    """Format an MB value compactly as MB or GB."""
    try:
        n=float(value or 0)
    except Exception:
        n=0.0
    if n >= 1024:
        gb=n/1024.0
        return f'{gb:.0f} GB' if gb >= 10 or abs(gb-round(gb)) < .05 else f'{gb:.1f} GB'
    return f'{int(round(n))} MB'

@register.simple_tag
def confidence_face(value):
    text=str(value or '').strip().lower()
    try:
        score=float(value)
        text='high' if score >= 75 else ('medium' if score >= 45 else 'low')
    except Exception:
        pass
    if any(x in text for x in ('skip','ignored','n/a','none')):
        mood='skipped'; mouth='<path d="M8.5 15.5l7-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'
    elif any(x in text for x in ('high','strong','good','yes')):
        mood='high'; mouth='<path d="M8.5 14c1.1 2.2 5.9 2.2 7 0" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>'
    elif any(x in text for x in ('medium','mid','moderate')):
        mood='medium'; mouth='<path d="M9 15h6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>'
    else:
        mood='low'; mouth='<path d="M8.5 16c1.1-2.2 5.9-2.2 7 0" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>'
    svg=f'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="9" cy="10" r="1" fill="currentColor"/><circle cx="15" cy="10" r="1" fill="currentColor"/>{mouth}</svg>'
    return mark_safe(f'<span class="confidence-face confidence-{mood}" title="{text.title() or "Confidence unavailable"}">{svg}</span>')

@register.simple_tag
def route_value(routes, stage):
    try:
        r=(routes or {}).get(stage) or {}
        return f"{r.get('provider','')}|{r.get('model','')}" if r.get('provider') else ''
    except Exception:
        return ''

@register.simple_tag
def route_field(routes, stage, field, default=''):
    try:
        return ((routes or {}).get(stage) or {}).get(field, default)
    except Exception:
        return default

@register.simple_tag
def route_fallback_value(routes, stage):
    try:
        r=(routes or {}).get(stage) or {}
        return f"{r.get('fallback_provider','')}|{r.get('fallback_model','')}" if r.get('fallback_provider') else ''
    except Exception:
        return ''

@register.filter
def dict_get(value, key):
    try:
        return value.get(key, '')
    except Exception:
        return ''

@register.filter
def get_item(value, key):
    """Compatibility alias used by filter/count templates."""
    return dict_get(value, key)

@register.filter
def human_number(value):
    try: n=float(value or 0)
    except Exception: n=0
    neg=n<0; n=abs(n)
    for div,suffix in ((1_000_000_000,'B'),(1_000_000,'M'),(1_000,'K')):
        if n>=div:
            out=f'{n/div:.1f}'.rstrip('0').rstrip('.')+suffix
            return '-'+out if neg else out
    out=f'{int(n):,}'
    return '-'+out if neg else out


@register.filter
def resource_number(value):
    """Compact very large Resource Usage counters without abbreviating sub-million values."""
    try:
        n=float(value or 0)
    except Exception:
        n=0.0
    neg=n < 0
    n=abs(n)
    for div,suffix in ((1_000_000_000_000,'T'),(1_000_000_000,'B'),(1_000_000,'M')):
        if n >= div:
            out=f'{n/div:.1f}'.rstrip('0').rstrip('.')+suffix
            return '-'+out if neg else out
    # Keep the actual integer below one million; grouping preserves readability without
    # replacing the value with a K suffix.
    out=f'{int(round(n)):,}'
    return '-'+out if neg else out


@register.filter
def metric_number(value):
    """Compact million-scale KPI values while preserving one decimal below the threshold."""
    try:
        n=float(value or 0)
    except Exception:
        n=0.0
    neg=n < 0
    n=abs(n)
    for div,suffix in ((1_000_000_000_000,'T'),(1_000_000_000,'B'),(1_000_000,'M')):
        if n >= div:
            out=f'{n/div:.1f}'.rstrip('0').rstrip('.')+suffix
            return '-'+out if neg else out
    if abs(n-round(n)) < 1e-9:
        out=f'{int(round(n)):,}'
    else:
        out=f'{n:,.1f}'.rstrip('0').rstrip('.')
    return '-'+out if neg else out


@register.filter
def public_url(value):
    """Hide ScoutBox-internal placeholder URLs from all user-facing templates."""
    text=str(value or '').strip()
    if not text:
        return ''
    try:
        host=(urllib.parse.urlsplit(text).hostname or '').lower()
    except Exception:
        host=''
    if host.endswith('.invalid') or host in {'manual.invalid','imported.invalid'}:
        return ''
    return text

_PLATFORM_COMPANY_ALIASES={
    'indeed','glassdoor','linkedin','ziprecruiter','simplyhired','monster','jobsdb','jobstreet','seek','wanted',
    'we work remotely','weworkremotely','remote ok','remoteok','remote co','wellfound','angel list','angellist','himalayas',
    'y combinator','yc work at a startup','work at a startup','hacker news','hackernews',
    'greenhouse','lever','ashby','ashbyhq','workday','workday jobs','myworkdayjobs','smartrecruiters','workable',
    'bamboohr','recruitee','teamtailor','personio','jobvite','taleo','icims','breezy','facebook','reddit','twitter','youtube','github','gitlab'
}
_PLATFORM_HOST_DOMAINS=(
    'indeed.com','glassdoor.com','linkedin.com','jobsdb.com','jobsdb.co.th','jobsdb.com.hk','jobstreet.com','seek.com.au','seek.co.nz','wanted.co.kr',
    'weworkremotely.com','remoteok.com','remote.co','wellfound.com','angel.co','himalayas.app','ycombinator.com','workatastartup.com','news.ycombinator.com',
    'greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com',
    'bamboohr.com','recruitee.com','teamtailor.com','personio.de','jobvite.com','taleo.net','icims.com','breezy.hr',
    'facebook.com','reddit.com','x.com','twitter.com','youtube.com','github.com','gitlab.com'
)
_FOREIGN_COMPANY_FRAGMENT_RE=re.compile(r'[\u1100-\u11ff\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\u0400-\u052f\u0600-\u06ff\u0750-\u077f\u0e00-\u0e7f\u1780-\u17ff]+')

def _platform_label_key(value):
    text=str(value or '').casefold()
    text=re.sub(r'\b(?:inc|llc|ltd|limited|corp|corporation|company|co|gmbh|plc|pty|group|holdings)\b',' ',text)
    return re.sub(r'[^a-z0-9]+',' ',text).strip()

def _platform_company_label(value):
    key=_platform_label_key(value)
    if not key:
        return False
    compact=key.replace(' ','')
    aliases={_platform_label_key(x) for x in _PLATFORM_COMPANY_ALIASES}
    compact_aliases={x.replace(' ','') for x in aliases}
    if key in aliases or compact in compact_aliases:
        return True
    suffix_words={'jobs','job','career','careers','work','startup','startups','who','is','hiring'}
    for alias in aliases:
        if alias and (key.startswith(alias+' ') or key.endswith(' '+alias) or (' '+alias+' ') in (' '+key+' ')):
            remainder=re.sub(r'(^| )'+re.escape(alias)+r'( |$)',' ',key).strip()
            if not remainder or set(remainder.split()).issubset(suffix_words):
                return True
    tokens={x for x in key.split() if x}
    brand_tokens={x.replace(' ','') for x in aliases}
    return bool(tokens and tokens.issubset(brand_tokens | suffix_words))

def _platform_host(value):
    host=str(value or '').strip().lower().strip('.').removeprefix('www.')
    if not host:
        return False
    if '://' in host or '/' in host:
        try: host=(urllib.parse.urlsplit(host).hostname or '').lower().strip('.').removeprefix('www.')
        except Exception: host=''
    if not host:
        return False
    labels={x for x in host.split('.') if x}
    brand_tokens={x.replace(' ','') for x in {_platform_label_key(a) for a in _PLATFORM_COMPANY_ALIASES}}
    return any(host==d or host.endswith('.'+d) for d in _PLATFORM_HOST_DOMAINS) or bool(labels.intersection(brand_tokens))

def _clean_scraped_company_label(value):
    text=clean_placeholder(value)
    if not text:
        return ''
    m=_FOREIGN_COMPANY_FRAGMENT_RE.search(text)
    if m and m.start()>0:
        prefix=text[:m.start()].strip(' -–—|·:;/,')
        if re.search(r'[A-Za-z]{2,}',prefix):
            text=prefix
    text=re.split(r'(?i)\b(?:new window|opens? in new|view who|applicants?|posted|promoted|save job|apply now)\b',text,1)[0].strip(' -–—|·:;/,')
    return text

@register.filter
def clean_display(value):
    return clean_placeholder(value)

@register.filter
def addressbook_list_summary(value):
    """Compact Address Book list copy while preserving the full stored summary elsewhere."""
    text=' '.join(str(value or '').split()).strip()
    if not text: return ''
    words=text.split()
    if len(words)<=35 and len(text)<=260: return text
    clipped=' '.join(words[:35])
    if len(clipped)>260: clipped=clipped[:260].rsplit(' ',1)[0]
    return clipped.rstrip(' ,;:-')+'…'


@register.filter
def job_title_clean(value):
    """Defensively remove stray non-Latin fragments from role titles before display.

    The release backfill persists the normalized value, but this filter prevents a legacy
    row from flashing an old mixed-script title while that background repair is pending.
    """
    return normalize_opportunity_title(clean_placeholder(value))[0]


_URL_CONTENT_WARNING_PREFIX='CONTENT_NOT_JOB:'


_HTTP_STATUS_TEXT={200:'OK',201:'Created',202:'Accepted',204:'No Content',301:'Moved Permanently',302:'Found',304:'Not Modified',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',410:'Gone',429:'Too Many Requests',500:'Internal Server Error',502:'Bad Gateway',503:'Service Unavailable',504:'Gateway Timeout'}

@register.filter
def url_health_tooltip(value):
    from django.utils import timezone
    status=getattr(value,'domain_http_status',None) if value.__class__.__name__=='Contact' else getattr(value,'target_http_status',None)
    checked=getattr(value,'domain_checked_at',None) if value.__class__.__name__=='Contact' else getattr(value,'target_checked_at',None)
    error=str(getattr(value,'domain_check_error','') if value.__class__.__name__=='Contact' else getattr(value,'target_check_error','') or '')
    size=int(getattr(value,'domain_response_bytes',0) if value.__class__.__name__=='Contact' else getattr(value,'target_response_bytes',0) or 0)
    if status is None: return error or 'URL health not checked'
    reason=_HTTP_STATUS_TEXT.get(int(status),'')
    line=f'HTTP {status}'+(f' {reason}' if reason else '')+(f' ({size:,} bytes)' if size and 200 <= int(status) < 400 else '')
    if checked:
        try: line+='\nChecked: '+timezone.localtime(checked).strftime('%d/%m/%Y %H:%M:%S')
        except Exception: pass
    if error: line+='\n'+url_health_message(error)
    return line

@register.filter
def url_health_content_warning(value):
    text=str(getattr(value,'target_check_error','') or getattr(value,'domain_check_error','') or (value if isinstance(value,str) else '') or '')
    return text.startswith(_URL_CONTENT_WARNING_PREFIX)

@register.filter
def url_health_message(value):
    text=str(value or '').strip()
    if text.startswith(_URL_CONTENT_WARNING_PREFIX):
        text=text[len(_URL_CONTENT_WARNING_PREFIX):].strip()
    return text

@register.filter
def url_health_stale(value):
    """Last-known health is retained but visually aged after recurring checks stop."""
    try:
        from django.utils import timezone
        from datetime import timedelta
        created=getattr(value,'first_seen_by_portal',None) or getattr(value,'created_at',None)
        return bool(created and created < timezone.now()-timedelta(days=90))
    except Exception:
        return False

_ROLE_TITLE_HINT=re.compile(r'(?i)\b(engineer|developer|consultant|architect|writer|technical|firmware|software|linux|embedded|systems?|principal|specialist|manager|director|lead|scientist|researcher|designer|devops|security|platform|kernel|administrator|analyst|programmer)\b')

def _role_title_looks_like_jd_sentence(value):
    text=' '.join(str(value or '').split()).strip()
    if not text:
        return True
    if text[:1] in {'•','·','▪','-'}:
        return True
    low=text.casefold()
    if low.startswith(('responsibilities','requirements','develop new ','design and ','work hands-on ','collaborate with ','focusing on ')):
        return True
    if len(text)>115 and (text.endswith('.') or text.count(',')>=2):
        return True
    return False

@register.filter
def opportunity_role_title(row):
    """Compact role label for list UIs without rewriting otherwise valid stored titles."""
    raw_title=clean_placeholder(getattr(row,'title',''))
    if _looks_urlish_display(raw_title):
        url_title=_role_from_urlish(raw_title)
        if url_title:
            return url_title
    title=normalize_opportunity_title(raw_title)[0]
    if title and not _looks_urlish_display(title) and not _role_title_looks_like_jd_sentence(title):
        return title
    facts=getattr(row,'extracted_facts',{}) if isinstance(getattr(row,'extracted_facts',None),dict) else {}
    refresh=facts.get('manual_metadata_refresh') if isinstance(facts.get('manual_metadata_refresh'),dict) else {}
    for src in refresh.get('sources') or []:
        candidate=' '.join(str((src or {}).get('title') or '').split()).strip(' -–—|·:;') if isinstance(src,dict) else ''
        if not candidate or len(candidate)>180 or _role_title_looks_like_jd_sentence(candidate) or not _ROLE_TITLE_HINT.search(candidate):
            continue
        # Remove a conservative company/site prefix, e.g. "Von Consulting - Software Engineer RTOS".
        company=' '.join(str(getattr(row,'company','') or '').split()).strip()
        if company and candidate.casefold().startswith(company.casefold()):
            candidate=candidate[len(company):].lstrip(' -–—|:')
        else:
            parts=re.split(r'\s+(?:-|–|—|\|)\s+',candidate,maxsplit=1)
            if len(parts)==2 and not _ROLE_TITLE_HINT.search(parts[0]) and _ROLE_TITLE_HINT.search(parts[1]):
                candidate=parts[1].strip()
        if candidate and _ROLE_TITLE_HINT.search(candidate):
            return sanitize_mixed_script_title(candidate[:180])
    url=str(getattr(row,'target_url','') or getattr(row,'url','') or '')
    try:
        slug=urllib.parse.urlsplit(url).path.rstrip('/').rsplit('/',1)[-1]
        slug=urllib.parse.unquote(slug)
    except Exception:
        slug=''
    if slug and not slug.isdigit():
        candidate=' '.join(x for x in re.split(r'[-_]+',slug) if x and not x.isdigit()).strip()
        if _ROLE_TITLE_HINT.search(candidate) and 4<=len(candidate)<=120:
            words=[]
            for word in candidate.split():
                low=word.lower()
                if low in {'rtos','fpga','linux','ios','ai','ml','qa','c','c++'}:
                    words.append(word.upper() if low not in {'linux','ios'} else word.title())
                else:
                    words.append(word.capitalize())
            return ' '.join(words)
    return title or 'Opportunity'



@register.filter
def concise_opportunity_summary(value):
    return concise_technical_summary(value)


_URLISH_DISPLAY_RE=re.compile(r'(?i)^(?:https?://|www\.)|/(?:jobs?|careers?|positions?|openings?)(?:/|$)|\.(?:com|io|ai|net|org|co|dev|app|jobs)(?:/|$)')
_URL_SLUG_STOPWORDS={'job','jobs','career','careers','position','positions','opening','openings','apply','application','work','with','us','remote'}

def _looks_urlish_display(value):
    text=' '.join(str(value or '').split()).strip()
    if not text:
        return False
    if _URLISH_DISPLAY_RE.search(text):
        return True
    try:
        parsed=urllib.parse.urlsplit(text if '://' in text else 'https://'+text)
        host=(parsed.hostname or '').lower()
        return bool(host and '.' in host and (parsed.path and parsed.path != '/'))
    except Exception:
        return False

def _brand_from_urlish(value):
    text=' '.join(str(value or '').split()).strip()
    if not text:
        return ''
    try:
        parsed=urllib.parse.urlsplit(text if '://' in text else 'https://'+text)
        host=(parsed.hostname or '').lower().strip('.').removeprefix('www.')
    except Exception:
        host=''
    if not host:
        return ''
    label=host.split('.')[0]
    if not label:
        return ''
    parts=[x for x in re.split(r'[-_]+',label) if x]
    if not parts:
        return host
    return ''.join(part[:1].upper()+part[1:] for part in parts)

def _role_from_urlish(value):
    text=' '.join(str(value or '').split()).strip()
    if not text:
        return ''
    try:
        parsed=urllib.parse.urlsplit(text if '://' in text else 'https://'+text)
        slug=urllib.parse.unquote((parsed.path or '').rstrip('/').rsplit('/',1)[-1])
    except Exception:
        slug=''
    if not slug or slug.isdigit():
        return ''
    words=[]
    for token in re.split(r'[-_+%20]+',slug):
        token=token.strip()
        if not token or token.isdigit() or token.lower() in _URL_SLUG_STOPWORDS:
            continue
        low=token.lower()
        if low in {'rtos','fpga','linux','ios','ai','ml','qa','api','apis','ui','ux','sre','devops'}:
            words.append(token.upper() if low not in {'linux','ios','devops'} else token[:1].upper()+token[1:])
        else:
            words.append(token.capitalize())
    candidate=' '.join(words).strip()
    return candidate if candidate and _ROLE_TITLE_HINT.search(candidate) else ''

@register.filter
def clean_company(value):
    text=_clean_scraped_company_label(value)
    if not text:
        return ''
    if _looks_urlish_display(text):
        brand=_brand_from_urlish(text)
        return brand if brand and not _platform_company_label(brand) and is_plausible_company_name(brand) else ''
    low=text.strip().lower()
    if low.startswith(('reason:', 'reason -', 'reason —', 'reason ')):
        return ''
    if low in {'unknown company','company not identified','not identified'}:
        return ''
    if _platform_company_label(text):
        return ''
    if not is_plausible_company_name(text):
        return ''
    display=display_company_name(text) or text
    return '' if _platform_company_label(display) or not is_plausible_company_name(display) or _looks_urlish_display(display) else display

@register.filter
def rich_content(value):
    return mark_safe(rich_html(value))

@register.filter
def fact_items(value):
    return human_facts(value)

@register.filter
def confidence_label(value):
    return confidence_band(value)

@register.filter
def country_flag(value):
    labels=location_labels(value)
    if len(labels) > 1:
        return '◇'
    if len(labels) == 1:
        region=location_icon(labels[0])
        if region:
            return region
        name=labels[0]
    else:
        name=clean_placeholder(value)
    codes={'Afghanistan': 'AF', 'Albania': 'AL', 'Algeria': 'DZ', 'American Samoa': 'AS', 'Andorra': 'AD', 'Angola': 'AO', 'Anguilla': 'AI', 'Antarctica': 'AQ', 'Antigua and Barbuda': 'AG', 'Argentina': 'AR', 'Armenia': 'AM', 'Aruba': 'AW', 'Australia': 'AU', 'Austria': 'AT', 'Azerbaijan': 'AZ', 'Bahamas': 'BS', 'Bahrain': 'BH', 'Bangladesh': 'BD', 'Barbados': 'BB', 'Belarus': 'BY', 'Belgium': 'BE', 'Belize': 'BZ', 'Benin': 'BJ', 'Bermuda': 'BM', 'Bhutan': 'BT', 'Bolivia': 'BO', 'Bolivia, Plurinational State of': 'BO', 'Bonaire, Sint Eustatius and Saba': 'BQ', 'Bosnia and Herzegovina': 'BA', 'Botswana': 'BW', 'Bouvet Island': 'BV', 'Brazil': 'BR', 'British Indian Ocean Territory': 'IO', 'Brunei': 'BN', 'Brunei Darussalam': 'BN', 'Bulgaria': 'BG', 'Burkina Faso': 'BF', 'Burundi': 'BI', 'Cabo Verde': 'CV', 'Cambodia': 'KH', 'Cameroon': 'CM', 'Canada': 'CA', 'Cayman Islands': 'KY', 'Central African Republic': 'CF', 'Chad': 'TD', 'Chile': 'CL', 'China': 'CN', 'Christmas Island': 'CX', 'Cocos (Keeling) Islands': 'CC', 'Colombia': 'CO', 'Comoros': 'KM', 'Congo': 'CG', 'Congo, The Democratic Republic of the': 'CD', 'Cook Islands': 'CK', 'Costa Rica': 'CR', 'Croatia': 'HR', 'Cuba': 'CU', 'Curaçao': 'CW', 'Cyprus': 'CY', 'Czech Republic': 'CZ', 'Czechia': 'CZ', "Côte d'Ivoire": 'CI', 'Denmark': 'DK', 'Djibouti': 'DJ', 'Dominica': 'DM', 'Dominican Republic': 'DO', 'Ecuador': 'EC', 'Egypt': 'EG', 'El Salvador': 'SV', 'Equatorial Guinea': 'GQ', 'Eritrea': 'ER', 'Estonia': 'EE', 'Eswatini': 'SZ', 'Ethiopia': 'ET', 'Falkland Islands (Malvinas)': 'FK', 'Faroe Islands': 'FO', 'Fiji': 'FJ', 'Finland': 'FI', 'France': 'FR', 'French Guiana': 'GF', 'French Polynesia': 'PF', 'French Southern Territories': 'TF', 'Gabon': 'GA', 'Gambia': 'GM', 'Georgia': 'GE', 'Germany': 'DE', 'Ghana': 'GH', 'Gibraltar': 'GI', 'Greece': 'GR', 'Greenland': 'GL', 'Grenada': 'GD', 'Guadeloupe': 'GP', 'Guam': 'GU', 'Guatemala': 'GT', 'Guernsey': 'GG', 'Guinea': 'GN', 'Guinea-Bissau': 'GW', 'Guyana': 'GY', 'Haiti': 'HT', 'Heard Island and McDonald Islands': 'HM', 'Holy See (Vatican City State)': 'VA', 'Honduras': 'HN', 'Hong Kong': 'HK', 'Hungary': 'HU', 'Iceland': 'IS', 'India': 'IN', 'Indonesia': 'ID', 'Iran': 'IR', 'Iran, Islamic Republic of': 'IR', 'Iraq': 'IQ', 'Ireland': 'IE', 'Isle of Man': 'IM', 'Israel': 'IL', 'Italy': 'IT', 'Jamaica': 'JM', 'Japan': 'JP', 'Jersey': 'JE', 'Jordan': 'JO', 'Kazakhstan': 'KZ', 'Kenya': 'KE', 'Kiribati': 'KI', "Korea, Democratic People's Republic of": 'KP', 'Korea, Republic of': 'KR', 'Kuwait': 'KW', 'Kyrgyzstan': 'KG', "Lao People's Democratic Republic": 'LA', 'Laos': 'LA', 'Latvia': 'LV', 'Lebanon': 'LB', 'Lesotho': 'LS', 'Liberia': 'LR', 'Libya': 'LY', 'Liechtenstein': 'LI', 'Lithuania': 'LT', 'Luxembourg': 'LU', 'Macao': 'MO', 'Macau': 'MO', 'Madagascar': 'MG', 'Malawi': 'MW', 'Malaysia': 'MY', 'Maldives': 'MV', 'Mali': 'ML', 'Malta': 'MT', 'Marshall Islands': 'MH', 'Martinique': 'MQ', 'Mauritania': 'MR', 'Mauritius': 'MU', 'Mayotte': 'YT', 'Mexico': 'MX', 'Micronesia, Federated States of': 'FM', 'Moldova': 'MD', 'Moldova, Republic of': 'MD', 'Monaco': 'MC', 'Mongolia': 'MN', 'Montenegro': 'ME', 'Montserrat': 'MS', 'Morocco': 'MA', 'Mozambique': 'MZ', 'Myanmar': 'MM', 'Namibia': 'NA', 'Nauru': 'NR', 'Nepal': 'NP', 'Netherlands': 'NL', 'New Caledonia': 'NC', 'New Zealand': 'NZ', 'Nicaragua': 'NI', 'Niger': 'NE', 'Nigeria': 'NG', 'Niue': 'NU', 'Norfolk Island': 'NF', 'North Korea': 'KP', 'North Macedonia': 'MK', 'Northern Mariana Islands': 'MP', 'Norway': 'NO', 'Oman': 'OM', 'Pakistan': 'PK', 'Palau': 'PW', 'Palestine': 'PS', 'Palestine, State of': 'PS', 'Panama': 'PA', 'Papua New Guinea': 'PG', 'Paraguay': 'PY', 'Peru': 'PE', 'Philippines': 'PH', 'Pitcairn': 'PN', 'Poland': 'PL', 'Portugal': 'PT', 'Puerto Rico': 'PR', 'Qatar': 'QA', 'Romania': 'RO', 'Russia': 'RU', 'Russian Federation': 'RU', 'Rwanda': 'RW', 'Réunion': 'RE', 'Saint Barthélemy': 'BL', 'Saint Helena, Ascension and Tristan da Cunha': 'SH', 'Saint Kitts and Nevis': 'KN', 'Saint Lucia': 'LC', 'Saint Martin (French part)': 'MF', 'Saint Pierre and Miquelon': 'PM', 'Saint Vincent and the Grenadines': 'VC', 'Samoa': 'WS', 'San Marino': 'SM', 'Sao Tome and Principe': 'ST', 'Saudi Arabia': 'SA', 'Senegal': 'SN', 'Serbia': 'RS', 'Seychelles': 'SC', 'Sierra Leone': 'SL', 'Singapore': 'SG', 'Sint Maarten (Dutch part)': 'SX', 'Slovakia': 'SK', 'Slovenia': 'SI', 'Solomon Islands': 'SB', 'Somalia': 'SO', 'South Africa': 'ZA', 'South Georgia and the South Sandwich Islands': 'GS', 'South Korea': 'KR', 'South Sudan': 'SS', 'Spain': 'ES', 'Sri Lanka': 'LK', 'Sudan': 'SD', 'Suriname': 'SR', 'Svalbard and Jan Mayen': 'SJ', 'Sweden': 'SE', 'Switzerland': 'CH', 'Syria': 'SY', 'Syrian Arab Republic': 'SY', 'Taiwan': 'TW', 'Taiwan, Province of China': 'TW', 'Tajikistan': 'TJ', 'Tanzania': 'TZ', 'Tanzania, United Republic of': 'TZ', 'Thailand': 'TH', 'Timor-Leste': 'TL', 'Togo': 'TG', 'Tokelau': 'TK', 'Tonga': 'TO', 'Trinidad and Tobago': 'TT', 'Tunisia': 'TN', 'Turkmenistan': 'TM', 'Turks and Caicos Islands': 'TC', 'Tuvalu': 'TV', 'Türkiye': 'TR', 'Uganda': 'UG', 'Ukraine': 'UA', 'United Arab Emirates': 'AE', 'United Kingdom': 'GB', 'United States': 'US', 'United States Minor Outlying Islands': 'UM', 'Uruguay': 'UY', 'Uzbekistan': 'UZ', 'Vanuatu': 'VU', 'Venezuela': 'VE', 'Venezuela, Bolivarian Republic of': 'VE', 'Viet Nam': 'VN', 'Vietnam': 'VN', 'Virgin Islands, British': 'VG', 'Virgin Islands, U.S.': 'VI', 'Wallis and Futuna': 'WF', 'Western Sahara': 'EH', 'Yemen': 'YE', 'Zambia': 'ZM', 'Zimbabwe': 'ZW', 'Åland Islands': 'AX'}
    codes.update({'Cape Verde':'CV','Democratic Republic of the Congo':'CD','Ivory Coast':'CI','Micronesia':'FM','Republic of the Congo':'CG','Turkey':'TR','Vatican City':'VA','USA':'US','US':'US','U.S.':'US','U.S.A.':'US','United States of America':'US','GB':'GB','UK':'GB','U.K.':'GB','Great Britain':'GB','Britain':'GB'})
    if name=='Remote worldwide': return '🌐'
    code=codes.get(name,'')
    return ''.join(chr(127397+ord(c)) for c in code) if code else ''


def _structured_country_labels(value, *, allow_multi_label=False):
    """Extract display-safe country labels from retained JSON-LD/location blobs.

    Older rows may contain a whole JobPosting/applicantLocationRequirements JSON
    value in either country or role_location. Some provider payloads are not valid
    JSON by the time they are stored (Python reprs, comma-separated dict fragments,
    or HTML-escaped snippets). This helper is intentionally defensive: it returns
    recognized country labels when the structure is compact and returns an empty
    list for huge/multi-country eligibility lists so raw JSON is never printed.
    """
    raw=' '.join(str(value or '').replace('&quot;','"').replace('&#34;','"').split()).strip()
    if not raw:
        return []
    jsonish=(raw[0] in '[{' or '"@type"' in raw[:600] or "'@type'" in raw[:600] or ('Country' in raw[:600] and ('"name"' in raw[:800] or "'name'" in raw[:800])))
    if not jsonish:
        return []
    aliases={
        'US':'United States','USA':'United States','U.S.':'United States','U.S.A.':'United States','United States of America':'United States',
        'GB':'United Kingdom','GBR':'United Kingdom','UK':'United Kingdom','U.K.':'United Kingdom','Great Britain':'United Kingdom','Britain':'United Kingdom',
        'Republic of Korea':'South Korea','Korea, Republic of':'South Korea',
    }
    names=[]
    def add(candidate):
        text=' '.join(str(candidate or '').split()).strip(' \"\'.:,;{}[]()')
        if not text:
            return
        text=aliases.get(text,aliases.get(text.upper(),text))
        for country in COUNTRIES:
            if text.casefold()==country.casefold():
                canonical='United States' if country=='United States of America' else country
                if canonical not in names:
                    names.append(canonical)
                return
    def walk(obj):
        if isinstance(obj,dict):
            typ=str(obj.get('@type') or obj.get('type') or '').casefold()
            if 'country' in typ:
                add(obj.get('name') or obj.get('alternateName'))
            for key in ('addressCountry','country','countryCode','name','alternateName'):
                if key in obj:
                    val=obj.get(key)
                    if isinstance(val,(dict,list)):
                        walk(val)
                    elif key != 'name' or 'country' in typ:
                        add(val)
            for val in obj.values():
                if isinstance(val,(dict,list)):
                    walk(val)
        elif isinstance(obj,list):
            for item in obj:
                walk(item)
        elif isinstance(obj,str):
            add(obj)
    parsed=None
    candidates=[raw]
    if raw.startswith('{') and re.search(r'}\s*,\s*{',raw):
        candidates.append('['+raw+']')
    for candidate in candidates:
        for loader in (json.loads, ast.literal_eval):
            try:
                parsed=loader(candidate)
                break
            except Exception:
                parsed=None
        if parsed is not None:
            break
    if parsed is not None:
        walk(parsed)
    if not names:
        pattern=r'["\'](?:(?:address)?country(?:Code)?|name|alternateName)["\']\s*:\s*["\']([^"\']+)["\']'
        for match in re.finditer(pattern, raw, re.I):
            add(match.group(1))
    if len(names)>1 and allow_multi_label:
        return ['Multiple countries']
    return names


@register.filter
def role_location_display(value):
    """Display a safe, concise role location and suppress raw JSON-LD/remote prose."""
    text=' '.join(str(value or '').replace('&quot;','"').replace('&#34;','"').split()).strip()
    if not text:
        return ''
    structured=_structured_country_labels(text, allow_multi_label=False)
    if len(structured)==1:
        return structured[0]
    if len(structured)>1 or text[0] in '[{' or '"@type"' in text[:600] or "'@type'" in text[:600]:
        return ''
    low=text.casefold()
    # Long work-arrangement prose belongs in the Remote column, not under Role / Company.
    remote_words=('remote','hybrid','work from home','home based','home-based','telecommute','teleworking','timezone','time zone','overlap','working hours','office hours','east africa','west africa','cest','cet','est','pst')
    if any(x in low for x in remote_words):
        country=country_only(text)
        return country if country else ''
    return text[:120]


@register.filter
def country_only(value):
    """Return a concise country label from a more detailed company location."""
    text=' '.join(str(value or '').split()).strip()
    if not text:
        return ''
    structured=_structured_country_labels(text)
    if len(structured)==1:
        return structured[0]
    if len(structured)>1:
        return ''
    labels=location_labels(text)
    if len(labels)==1:
        return labels[0]
    low=text.casefold()
    if low in {'remote','fully remote','hybrid','on-site','onsite'}:
        return ''
    canonical={
        'us':'United States','u.s.':'United States','u.s.a.':'United States','usa':'United States','united states of america':'United States',
        'uk':'United Kingdom','u.k.':'United Kingdom','gb':'United Kingdom','great britain':'United Kingdom','britain':'United Kingdom',
        'uae':'United Arab Emirates','republic of korea':'South Korea','korea, republic of':'South Korea',
    }
    def normalized(candidate):
        candidate=' '.join(str(candidate or '').split()).strip(' .-–—|;/')
        if not candidate:
            return ''
        direct=canonical.get(candidate.casefold(),candidate)
        return direct if country_flag(direct) else ''
    direct=normalized(text)
    if direct:
        return direct
    # Company research commonly returns "City, Region, Country" or uses separators.
    parts=[x.strip() for x in re.split(r'\s*(?:,|\||;|·|—|–)\s*',text) if x.strip()]
    for candidate in reversed(parts):
        result=normalized(candidate)
        if result:
            return result
    # Country combinations such as "UK or US" cannot render multiple flags in the
    # compact list. Pick the first explicitly named country, preserving deterministic order.
    matches=[]
    for name in sorted(COUNTRIES,key=len,reverse=True):
        aliases=[name]
        if name=='United States': aliases += ['USA','US','U.S.','United States of America']
        if name=='United Kingdom': aliases += ['UK','U.K.','Great Britain','Britain']
        for alias in aliases:
            m=re.search(r'(?i)(?<![A-Za-z])'+re.escape(alias)+r'(?![A-Za-z])',text)
            if m: matches.append((m.start(),len(alias),name)); break
    if matches:
        matches.sort(key=lambda x:(x[0],-x[1]))
        return matches[0][2]
    # Last-resort suffix matching for strings such as "Tokyo Japan" without punctuation.
    for name in sorted(COUNTRIES,key=len,reverse=True):
        if re.search(r'(?i)(?:^|[\s,])'+re.escape(name)+r'\s*$',text):
            return canonical.get(name.casefold(),name)
    return ''


@register.filter
def clean_area_keywords(value):
    text=str(value or '').strip()
    pattern=re.compile(r'^\s*(?:relevant\s+(?:technical\s+)?(?:work|areas?|experience|skills?|signals?)|technical\s+areas?|areas?)\s*:\s*',re.I)
    while text:
        newer=pattern.sub('',text,count=1).strip()
        if newer==text:
            break
        text=newer
    return text

@register.filter(name='area_keywords')
def area_keywords(value):
    return clean_area_keywords(value)

@register.simple_tag
def fit_signal(value):
    try: score=max(0,min(100,int(value or 0)))
    except Exception: score=0
    level=1 if score < 35 else (2 if score < 55 else (3 if score < 70 else (4 if score < 85 else 5)))
    bars=[]
    for i,h in enumerate((5,8,11,14,17),1):
        cls='active' if i<=level else 'inactive'
        bars.append(f'<rect class="{cls}" x="{2+(i-1)*4}" y="{20-h}" width="2.6" height="{h}" rx="1"/>')
    return mark_safe(f'<span class="fit-signal fit-level-{level}" aria-label="Fit score {score} out of 100"><svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true">{"".join(bars)}</svg></span>')


@register.simple_tag
def fit_face(value):
    """Compact two-digit Fit badge with discovery provenance encoded in the border."""
    entity=value if hasattr(value,'__dict__') else None
    raw_score=value
    if entity is not None:
        raw_score=getattr(entity,'fit_score',None)
        if raw_score is None:
            raw_score=getattr(entity,'score',None)
        if raw_score is None:
            try:
                intel=getattr(entity,'company_intel',{}) or {}
                fit=intel.get('fit_classification') if isinstance(intel,dict) and isinstance(intel.get('fit_classification'),dict) else {}
                raw_score=fit.get('score')
            except Exception:
                raw_score=None
    if entity is not None and entity.__class__.__name__=='Contact':
        try:
            intel=getattr(entity,'company_intel',{}) or {}
            fit=intel.get('fit_classification') if isinstance(intel,dict) and isinstance(intel.get('fit_classification'),dict) else {}
            assessed=('score' in fit and fit.get('score') not in (None,''))
        except Exception:
            assessed=False
        if not assessed:
            inherited=intel.get('inherited_fit') if isinstance(intel,dict) and isinstance(intel.get('inherited_fit'),dict) else {}
            if inherited.get('score') not in (None,''):
                try: inherited_score=max(0,min(100,int(inherited.get('score')))); return mark_safe(f'<span class="fit-score-badge fit-band-medium fit-origin-local" title="Inherited Fit: {inherited_score}/100\nTemporary fallback from originating Opportunity/Hidden Lead; direct Address Book assessment pending." aria-label="Inherited Fit {inherited_score} out of 100">{min(99,max(10,inherited_score)):02d}</span>')
                except Exception: pass
            failure=intel.get('fit_assessment_error') if isinstance(intel,dict) else ''
            reason=str(failure or 'Direct Address Book Fit assessment has not succeeded; insufficient evidence or provider unavailable.')[:260]
            return mark_safe(f'<span class="fit-score-unassessed" title="{escape(reason)}" aria-label="Fit not assessed">?</span>')
    try: score=max(0,min(100,int(raw_score if raw_score not in (None,'') else 0)))
    except Exception: score=0

    # Keep a stable two-character footprint in dense list cells. Very small non-zero
    # scores are displayed as 10 and a perfect 100 as 99; the exact raw score remains
    # available in the tooltip and is still the value used for sorting.
    display_score=0 if score<=0 else (10 if score<10 else (99 if score>=100 else score))
    if score < 35:
        band='poor'; label='Poor fit'
    elif score < 55:
        band='low'; label='Low fit'
    elif score < 75:
        band='medium'; label='Medium fit'
    else:
        band='high'; label='High fit'

    confidence=0
    if entity is not None:
        try:
            facts=getattr(entity,'extracted_facts',{}) or {}
            if not facts and hasattr(entity,'ai_state'):
                facts=getattr(entity,'ai_state',{}) or {}
            if not facts and hasattr(entity,'company_intel'):
                facts=getattr(entity,'company_intel',{}) or {}
            fc=facts.get('fit_classification') if isinstance(facts,dict) and isinstance(facts.get('fit_classification'),dict) else {}
            cloud=facts.get('cloud_research') if isinstance(facts,dict) and isinstance(facts.get('cloud_research'),dict) else {}
            for candidate in (fc.get('confidence'),cloud.get('confidence'),facts.get('confidence') if isinstance(facts,dict) else None):
                if candidate in (None,''): continue
                if isinstance(candidate,str) and not candidate.strip().isdigit():
                    text=candidate.strip().casefold(); confidence=25 if text.startswith('low') else (60 if text.startswith('medium') else (85 if text.startswith('high') else 0))
                else: confidence=max(0,min(100,int(candidate)))
                if confidence: break
        except Exception: confidence=0
        if not confidence and hasattr(entity,'score') and not hasattr(entity,'fit_score'):
            confidence=score
    if confidence<=0: confidence_label='Unavailable'
    elif confidence>=75: confidence_label='High'
    elif confidence>=45: confidence_label='Medium'
    else: confidence_label='Low'

    origin_class='fit-origin-cloud'
    origin_label='Cloud entry'
    origin_note=''
    if entity is not None:
        try:
            origin=_discovery_origin(entity)
            if origin.get('effective')=='local':
                origin_class='fit-origin-local'
                origin_label='Local entry' if origin.get('css')!='legacy' else 'Legacy entry (treated as local)'
                origin_note='\nRe-evaluate for better accuracy.'
            else:
                origin_label='Cloud-verified entry' if origin.get('css')=='local-cloud' else 'Cloud entry'
        except Exception:
            origin_class='fit-origin-local'; origin_label='Legacy entry (treated as local)'; origin_note='\nRe-evaluate for better accuracy.'
    fit_detail=''
    if entity is not None:
        try:
            intel=getattr(entity,'company_intel',{}) or {}
            fc=intel.get('fit_classification') if isinstance(intel,dict) and isinstance(intel.get('fit_classification'),dict) else {}
            provider=str(fc.get('provider') or '').strip(); model=str(fc.get('model') or '').strip(); reason=str(fc.get('reason') or '').strip()
            if provider or model: fit_detail+='\nAssessment: '+(' · '.join(x for x in (provider,model) if x))
            if reason: fit_detail+='\nReason: '+reason[:400]
        except Exception: pass
    title=f'Fit score: {score}/100\n{label}\nAssessment confidence: {confidence_label}\nSource: {origin_label}{origin_note}{fit_detail}'
    aria=f'Fit score {score} out of 100, {label}; assessment confidence {confidence_label}; source {origin_label}'
    return mark_safe(f'<span class="fit-score-badge fit-band-{band} {origin_class}" title="{escape(title)}" aria-label="{escape(aria)}">{display_score:02d}</span>')

@register.filter
def fit_band(value):
    try:n=int(value or 0)
    except Exception:n=0
    return 'high' if n>=80 else ('medium' if n>=55 else 'low')

@register.filter
def score_or_dash(value):
    try:
        if value in (None, ''): return '—'
        return str(max(0,min(100,int(value))))
    except Exception:
        return '—'


@register.filter
def manual_filter_provider(result):
    """Best-effort provider label for current and historical manual-filter jobs."""
    if not isinstance(result, dict):
        return ''
    value=str(result.get('provider') or '').strip()
    if value:
        return value
    for row in result.get('items') or []:
        if isinstance(row, dict):
            value=str(row.get('provider') or '').strip()
            if value:
                return value
    return ''


@register.filter
def manual_filter_model(result):
    """Best-effort model label for current and historical manual-filter jobs."""
    if not isinstance(result, dict):
        return ''
    value=str(result.get('model') or '').strip()
    if value:
        return value
    for row in result.get('items') or []:
        if isinstance(row, dict):
            value=str(row.get('model') or '').strip()
            if value:
                return value
    return ''


@register.filter
def manual_filter_fit_change(row):
    """Readable Fit delta; old filter jobs did not recalculate/store Fit."""
    if not isinstance(row, dict):
        return 'Not recalculated'
    before=row.get('fit_before')
    after=row.get('fit_after')
    if before in (None, '') and after in (None, ''):
        return 'Not recalculated'
    return f'{score_or_dash(before)} → {score_or_dash(after)}'


@register.filter
def manual_filter_fit_sort_value(row):
    """Numeric post-re-evaluation Fit value used by sortable history tables."""
    if not isinstance(row, dict):
        return -1
    value=row.get('fit_after')
    if value in (None, ''):
        value=row.get('fit_before')
    try:
        return int(float(value))
    except Exception:
        return -1


@register.filter
def manual_filter_strong_fit(result, threshold=75):
    """Count surviving result rows whose post-filter Fit meets the threshold.

    Recycled/failed rows are not "still" good fits. Historical runs that predate
    fit_after simply contribute zero rather than guessing from the current database.
    """
    if not isinstance(result, dict):
        return 0
    try:
        threshold=int(threshold or 75)
    except Exception:
        threshold=75
    count=0
    for row in result.get('items') or []:
        if not isinstance(row, dict):
            continue
        decision=str(row.get('decision') or '').strip().lower()
        if decision in {'recycled','failed','timeout','timed_out'}:
            continue
        value=row.get('fit_after')
        if value in (None, ''):
            continue
        try:
            if int(value) >= threshold:
                count += 1
        except Exception:
            continue
    return count


@register.filter
def manual_filter_count(result, key):
    """Return a numeric manual-filter count, with stable aliases for templates."""
    try:
        if key in ('strong', 'strong_fit', 'strong_fit_count'):
            return int(manual_filter_strong_fit(result) or 0)
        data = result if isinstance(result, dict) else {}
        aliases = {
            'processed': ('processed', 'checked', 'total_processed'),
            'kept': ('kept', 'keep'),
            'recycled': ('recycled', 'recycle'),
            'protected': ('protected',),
            'review': ('review', 'need_review', 'needs_review'),
            'failed': ('failed', 'errors', 'error_count'),
            'timed_out': ('timed_out', 'timeout', 'timeouts'),
            'skipped': ('skipped', 'skip'),
        }
        for name in aliases.get(str(key), (str(key),)):
            value = data.get(name, 0)
            if value not in (None, ''):
                return max(0, int(float(value)))
    except Exception:
        return 0
    return 0


def _manual_filter_display_counts(result):
    """Collapse internal review/protection/conversion states into user-facing outcomes.

    Re-evaluation history is intentionally a three-state result surface: Keep, Recycle,
    or Failed.  Internal states still remain in the stored job result for diagnostics.
    """
    data=result if isinstance(result,dict) else {}
    processed=manual_filter_count(data,'processed')
    recycled=manual_filter_count(data,'recycled')
    failed=manual_filter_count(data,'failed')+manual_filter_count(data,'timed_out')
    raw_kept=(manual_filter_count(data,'kept')+manual_filter_count(data,'review')+
              manual_filter_count(data,'protected')+manual_filter_count(data,'skipped')+
              manual_filter_count(data,'converted_to_hidden_lead')+manual_filter_count(data,'converted_to_opportunity'))
    if processed:
        kept=max(raw_kept,processed-recycled-failed)
    else:
        kept=raw_kept
        processed=kept+recycled+failed
    return {'processed':max(0,processed),'kept':max(0,kept),'recycled':max(0,recycled),'failed':max(0,failed)}


@register.filter
def manual_filter_display_count(result,key):
    try:
        return int(_manual_filter_display_counts(result).get(str(key),0) or 0)
    except Exception:
        return 0


@register.filter
def manual_filter_decision_label(row):
    decision=str((row or {}).get('decision') if isinstance(row,dict) else row or '').strip().lower()
    if decision in {'failed','timeout','timed_out','error'}:
        return 'Failed'
    if decision in {'recycled','recycle','reject','rejected'}:
        return 'Recycle'
    return 'Keep'


@register.filter
def manual_filter_decision_class(row):
    label=manual_filter_decision_label(row)
    return 'red' if label=='Failed' else ('amber' if label=='Recycle' else 'green')


@register.filter
def manual_filter_is_recycled(row):
    """True for every stored decision that the result UI normalizes to Recycle."""
    return manual_filter_decision_label(row) == 'Recycle'


def _manual_filter_is_placeholder_value(value):
    text=str(value or '').strip().lower()
    return text in {'', '-', '—', 'not recalculated', 'not calculated', 'n/a', 'none', 'null'}


def _manual_filter_has_numeric_score(row):
    if not isinstance(row, dict):
        return False
    for key in ('fit_after', 'lead_score', 'fit_before', 'confidence'):
        value=row.get(key)
        if value in (None, ''):
            continue
        text=str(value).strip().replace('%','')
        if text.lower() in {'not recalculated','not calculated','n/a','none','null','-','—'}:
            continue
        try:
            float(text)
            return True
        except Exception:
            continue
    return False


def _manual_filter_item_is_meaningful(row):
    """Return True only for rows with useful, user-visible reassessment detail.

    Legacy/interrupted runs often stored placeholder rows such as:
    Hidden Lead # / Review / Not recalculated / 0% / —.  Those rows should not
    make a run visible in the latest-result banner or history dialog.
    """
    if not isinstance(row, dict):
        return False
    decision=str(row.get('decision') or '').strip().lower()
    applied=str(row.get('applied_decision') or '').strip().lower()
    name=str(row.get('company') or row.get('title') or row.get('email') or '').strip()
    # Generic/default labels are not real entry identity.
    if name.lower() in {'hidden lead', 'hidden lead #', 'opportunity', 'opportunity #', 'address book contact', 'contact', 'contact #'}:
        name=''
    reason=str(row.get('reason') or row.get('fit_reason') or '').strip()
    if _manual_filter_is_placeholder_value(reason):
        reason=''
    has_score=_manual_filter_has_numeric_score(row)
    # 0% confidence without a reason/score/name is not meaningful.
    try:
        confidence=float(str(row.get('confidence') or '').replace('%','').strip())
    except Exception:
        confidence=None
    has_nonzero_confidence=confidence is not None and confidence > 0
    has_details=bool(
        row.get('metadata_refreshed') or row.get('metadata_changes') or
        row.get('web_sources') or row.get('pages') or row.get('rejection_risks') or
        row.get('refreshed')
    )
    if decision in {'keep','admit','recycled','recycle','protected','failed','error','timeout','timed_out','reject','rejected'}:
        return bool(name or reason or has_score or has_nonzero_confidence or has_details)
    if applied and applied not in {'review'}:
        return bool(name or reason or has_score or has_nonzero_confidence or has_details)
    return bool(name and (reason or has_score or has_nonzero_confidence or has_details))

@register.filter
def manual_filter_meaningful_items(result):
    if not isinstance(result, dict):
        return []
    return [row for row in (result.get('items') or []) if _manual_filter_item_is_meaningful(row)]


@register.filter
def manual_filter_has_meaningful_result(result):
    """Hide empty/placeholder re-evaluation result cards.

    A run is meaningful only when it has a final action/error or per-entry rows
    with real names, scores, refreshed fields, or reasons. Review-only placeholder
    rows such as “Hidden Lead # / Not recalculated / 0% / —” are intentionally
    hidden so the banner does not keep popping up with useless output.
    """
    if not isinstance(result, dict):
        return False
    for key in ('kept','admitted','recycled','rejected','protected','timed_out','failed','errors'):
        try:
            if int(result.get(key) or 0) > 0:
                return True
        except Exception:
            pass
    if result.get('fatal_error') or result.get('error') or result.get('circuit_breaker'):
        return True
    return bool(manual_filter_meaningful_items(result))


@register.filter
def lead_note_display(value):
    """Remove contact-only boilerplate; structured Contact owns email/contact URL."""
    text=str(value or '').replace(' · ', '\n')
    lines=[]
    for raw in text.splitlines():
        line=raw.strip()
        if not line:
            continue
        if re.fullmatch(r'(?i)(?:contact\s+)?email\s*:\s*[^@\s]+@[^@\s]+\.[^@\s]+[.,;]?', line):
            continue
        if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+[.,;]?', line):
            continue
        if re.fullmatch(r'(?i)(?:contact\s+(?:form|link|url)|website\s+contact)\s*:\s*https?://\S+', line):
            continue
        if re.match(r'(?i)^cloud\s+outreach\s+path\s*:', line):
            continue
        if re.match(r'(?i)^previous\s+opportunit(?:y|ies)\b.*\bunsuitable\b', line):
            continue
        if re.match(r'(?i)^from\s+unsuitable\s+opportunit(?:y|ies)\b', line):
            continue
        lines.append(line)
    return '\n'.join(lines).strip()


def _compact_list_text(value, max_words=50):
    """Human list preview: plain text, compact whitespace, and a hard word budget."""
    text=strip_tags(str(value or ''))
    text=re.sub(r'(?i)https?://\S+', '', text)
    text=re.sub(r'\s+', ' ', text).strip(' \t\r\n-–—|·:;')
    if not text:
        return ''
    words=text.split()
    if len(words)<=max_words:
        return text
    return ' '.join(words[:max_words]).rstrip(' ,;:-')+'…'


def _hidden_lead_summary_noise(value):
    """True for non-descriptive summary values after extraction labels are removed."""
    raw=strip_tags(str(value or ''))
    raw=strip_hidden_lead_evidence_markers(raw)
    text=re.sub(r'\s+',' ',raw).strip(' \t\r\n-–—|·:;.').casefold()
    if not text:
        return False
    normalized=re.sub(r'[_-]+',' ',text)
    normalized=re.sub(r'\s+',' ',normalized).strip()
    enum_values={
        'summary pending','full time','part time','contract','contractor','collaboration','agency consulting',
        'one time project','unknown','fully remote','remote','hybrid','onsite','on site',
    }
    if normalized in enum_values:
        return True
    match=re.fullmatch(r'(?:employment type|engagement type|job type|engagement|employment)\s*:?\s*(.+)',normalized)
    return bool(match and match.group(1).strip() in enum_values)


def _sentence_start(value):
    """Uppercase the first alphabetic character without lowercasing the rest."""
    text=str(value or '').strip()
    for index,char in enumerate(text):
        if char.isalpha():
            return text[:index]+char.upper()+text[index+1:]
    return text


@register.filter
def usable_hidden_lead_summary(value):
    """Return readable Hidden Lead prose with extraction labels removed."""
    clean=strip_hidden_lead_evidence_markers(strip_tags(str(value or '')))
    return '' if _hidden_lead_summary_noise(clean) else _sentence_start(clean)


def _useful_opportunity_text(value):
    text=_compact_list_text(value, 90)
    if not text:
        return ''
    low=text.casefold()
    boilerplate=(
        'discovery candidate verified against the target page',
        'enrichment/ranking pending',
        'cloud web research verified this opportunity',
        'remote eligibility could not be confirmed',
        'qualification flagged this page as non-role content',
        'imported historical application',
    )
    if any(x in low for x in boilerplate) and len(text.split()) < 24:
        return ''
    # Fit explanations that talk mainly about the candidate/profile are not useful as
    # the list's role-specific "what is special here" summary.
    candidate_markers=("candidate's background",'candidate background','candidate profile','profile aligns','fit score')
    if any(x in low for x in candidate_markers) and not any(x in low for x in ('remote','travel','firmware','embedded','kernel','reverse','qemu','dspic','arm','virtual','security','protocol','legacy')):
        return ''
    return text


@register.filter
def opportunity_list_summary(opportunity):
    """Short, concrete JD-grounded cue for the Opportunity list."""
    grounded=opportunity_specific_highlight(opportunity)
    if grounded:
        return grounded
    # Preserve a legacy stored cue only when no retained JD evidence can produce a better
    # signal. Keep it terse so recommendation prose cannot dominate the list column.
    return concise_technical_summary(getattr(opportunity,'list_highlight',''))


@register.simple_tag(takes_context=True)
def opportunity_salary(context, opportunity):
    """Render useful numeric compensation only; hide absent/noisy salary placeholders."""
    from portal.services.salary import (salary_preference_match, source_label,
                                        salary_text_has_numeric_amount, salary_urls_equivalent)
    profile=context.get('profile')
    if profile is None:
        try:
            from portal.models import Profile
            profile=Profile.objects.first()
        except Exception:
            profile=None
    text=str(getattr(opportunity,'salary_text','') or '').strip()
    text=re.sub(r'(?i)\s*job\s+post(?:ing)?\s*$', '', text).strip(' √|·-')
    if not salary_text_has_numeric_amount(text):
        return ''
    match=salary_preference_match(opportunity,profile) if profile else {'state':'unknown'}
    state=match.get('state','unknown')
    source=source_label(opportunity)
    source_url=str(getattr(opportunity,'salary_source_url','') or '').strip()
    role_url=str(getattr(opportunity,'target_url','') or getattr(opportunity,'url','') or '').strip()
    # The job-post URL is already visible in the first cell. Link only genuinely separate
    # salary evidence (external research / market source), avoiding redundant links.
    source_kind=str(getattr(opportunity,'salary_source_type','') or '').casefold()
    show_source_link=(source_kind in {'external','market'} and source_url.startswith(('http://','https://')) and not salary_urls_equivalent(source_url,role_url))
    is_job_post=source_kind in {'post','job_post','job-post'} or str(source or '').strip().casefold() in {'job post','job posting'}
    provenance=(('<a href="'+escape(source_url)+'" target="_blank" rel="noreferrer">'+escape(source)+'</a>') if show_source_link else ('' if is_job_post else escape(source)))
    meta=provenance if provenance else ''
    small=('<small>'+meta+'</small>') if meta else ''
    tooltip=' title="Salary information from job post"' if is_job_post else ''
    return mark_safe('<div class="opportunity-salary salary-'+escape(state)+'"'+tooltip+'><span class="salary-icon" aria-hidden="true">$</span><span>'+escape(text)+'</span>'+small+'</div>')


def _compact_hidden_lead_summary(value, company=''):
    """List-only Hidden Lead preview: compact company/technical facts, not outreach prose."""
    text=strip_tags(str(value or ''))
    text=re.sub(r'(?i)https?://\S+', '', text)
    text=re.sub(r'\s+', ' ', text).strip(' \t\r\n-–—|·:;')
    if not text:
        return ''
    # The company already has its own column. Drop common biography-style openings and
    # candidate-facing filler so the list answers "what do they do?" quickly.
    text=re.sub(r'(?i)^founded\s+[^,.;]{0,90}[,;]\s*', '', text).strip()
    name=re.escape(str(company or '').strip())
    if name:
        text=re.sub(rf'(?i)^{name}\s+(?:is|are)\s+(?:an?\s+)?', '', text).strip()
        text=re.sub(rf'(?i)^{name}\s*[-–—:]\s*', '', text).strip()
    sentences=[x.strip() for x in re.split(r'(?<=[.!?])\s+', text) if x.strip()]
    useful=[]
    filler_starts=(
        'for engineers','for systems','for candidates','for developers','for professionals',
        'it provides a realistic path','this provides a realistic path','this may be',
        'it may be','explore whether','this could be','this makes it','a good fit for',
    )
    for sentence in sentences:
        if sentence.casefold().startswith(filler_starts):
            continue
        useful.append(sentence)
        if len(' '.join(useful).split())>=20:
            break
    text=' '.join(useful) if useful else text
    # Hidden Leads get a little more context than Opportunity rows, but remain scan-friendly.
    return _compact_list_text(text,30)


@register.filter
def hidden_lead_list_summary(lead):
    """Compact the best readable Hidden Lead text without exposing extraction labels."""
    company=getattr(lead,'company','')
    stored=getattr(lead,'summary','')
    clean_stored=strip_hidden_lead_evidence_markers(stored)
    if clean_stored and not _hidden_lead_summary_noise(clean_stored) and not hidden_lead_summary_is_generic(clean_stored):
        text=_compact_hidden_lead_summary(clean_stored,company)
        if text:
            return _sentence_start(text)
    retained=company_summary_from_intel(getattr(lead,'company_intel',{}) or {},900)
    clean_retained=strip_hidden_lead_evidence_markers(retained)
    if clean_retained and not hidden_lead_summary_is_generic(clean_retained):
        text=_compact_hidden_lead_summary(clean_retained,company)
        if text:
            return _sentence_start(text)
    # While the refined company summary is still being generated, show a compact source
    # excerpt rather than a placeholder. Extraction labels are metadata, so strip them
    # and preserve the useful sentence(s) after the bracket.
    evidence=strip_hidden_lead_evidence_markers(getattr(lead,'evidence',''))
    if evidence:
        text=_compact_hidden_lead_summary(evidence,company)
        if text:
            return _sentence_start(text)
    return ''


def _discovery_origin(entity):
    # Kept as a template-layer compatibility wrapper; provenance is shared with views.
    return fit_assessment_origin(entity)


@register.simple_tag
def discovery_origin_badge(entity):
    data=_discovery_origin(entity)
    return mark_safe('<span class="discovery-origin-badge discovery-origin-'+escape(data['css'])+'" title="'+escape(data['title'])+'">'+escape(data['label'])+'</span>')


@register.filter
def opportunity_note_display(value):
    """Short list-only rendering for distinctive Cloud discovery notes."""
    text=' '.join(str(value or '').split()).strip()
    if not text:
        return ''
    generated=bool(re.match(r'(?i)^discovery\s+signal\s*:', text))
    text=re.sub(r'(?i)^discovery\s+signal\s*:\s*', '', text).strip()
    markers=('retro','legacy','niche','hard to find','hard-to-find','rare','unusual','specialist','reverse engineering','obsolete','vintage')
    if generated and not any(m in text.casefold() for m in markers):
        return ''
    limit=135
    if len(text)>limit:
        text=text[:limit].rsplit(' ',1)[0].rstrip(' ,;:-')
    return text

@register.filter
def company_location(value):
    """Company/HQ location for list views; supports countries and recruiter regions."""
    labels=location_labels(value)
    if labels:
        return location_display_text(labels, limit=4)
    text=' '.join(str(value or '').split()).strip()
    low=text.casefold()
    if not text:
        return ''
    if low.strip(' .-_/') in {'unknown','not set','not specified','unspecified','n/a','na','none','null','tbd','other','others'}:
        return ''
    if low in {'remote','fully remote','hybrid','on-site','onsite','distributed'}:
        return ''
    structured=_structured_country_labels(text,allow_multi_label=True)
    if structured:
        return structured[0]
    if text[0] in '[{':
        return ''
    return country_only(text) or text


@register.filter
def post_age_display_label(opportunity):
    """Return only ScoutBox age buckets; never leak evidence/method labels into KPI text."""
    return _freshness_post_age_display_label(opportunity)


@register.filter
def post_age_quality(opportunity):
    """Encode freshness confidence by colour only; age remains the human-readable label."""
    label=post_age_display_label(opportunity)
    try: confidence=int(getattr(opportunity,'freshness_confidence',0) or 0)
    except Exception: confidence=0
    if label=='Age unknown' or confidence<=0:
        return 'post-age-quality-none'
    if confidence>=75:
        return 'post-age-quality-high'
    if confidence>=45:
        return 'post-age-quality-medium'
    return 'post-age-quality-low'


@register.filter
def post_age_sort_value(opportunity):
    """Numeric Post Age value for markup; blank means the visible value is unknown."""
    value=opportunity_post_age_sort_days(opportunity)
    return '' if value is None else value


@register.filter
def age_short_label(value):
    label=str(value or '').strip()
    mapping={
        '< 1 week':'<3d', '<3 days':'<3d', '< 3 days':'<3d', '~1 week':'~1w', '~ 1 week':'~1w', '~2 weeks':'~2w', '~1 month':'~1mo', '~2 months':'~2mo', '~3 months':'~3mo',
        '~4 months':'~4mo', '~5 months':'~5mo', '~6 months':'~6mo',
        'Older / uncertain':'Likely Old', 'Stale / uncertain':'Likely Old', 'Old / uncertain':'Likely Old', 'Likely Old':'Likely Old', 'Age unknown':'?',
        'Ever-green':'Evergreen', 'Evergreen':'Evergreen', 'Evergreen Post':'Evergreen',
        # Backward-compatible labels from older releases.
        '≤ 7 days':'<3d','≤ 1 month':'~1mo','≤ 3 months':'~3mo','≤ 6 months':'~6mo',
        '≤ 1 year':'Old?','> 1 year':'Old?','Within 7 days':'<3d','Within 1 month':'~1mo',
        'Within 3 months':'~3mo','Within 6 months':'~6mo','Within 1 year':'Old?','Over 1 year':'Old?',
    }
    return mapping.get(label,'?')



@register.filter
def company_info_compact(value):
    # One compact age/size line. Unknown is intentionally just a question mark.
    age,size,age_kind,domain_age_domain,domain_registered_at=_company_info_parts(value)
    if age and size: return f'{age} · {size}'
    return age or size or '?'

def _employee_size_band(n):
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


def _employee_number(value):
    text=str(value or '').strip().lower()
    if not text: return 0
    text=re.sub(r'(?<=\d),(?=\d)','',text)
    m=re.search(r'(?<!\d)(\d+(?:\.\d+)?)\s*(k|thousand|m|million)?(?!\w)',text,re.I)
    if not m: return 0
    n=float(m.group(1)); suffix=(m.group(2) or '').lower()
    if suffix in {'k','thousand'}: n*=1000
    elif suffix in {'m','million'}: n*=1000000
    return int(round(n))


def _normalize_company_size_display(value):
    """Return a coarse, display-safe employee-size band instead of an exact headcount."""
    text=str(value or '').strip().replace('—','–')
    if not text: return ''
    clean=re.sub(r'(?<=\d),(?=\d)','',text)
    m=re.search(r'(?<!\d)(\d+(?:\.\d+)?)\s*(k|thousand|m|million)?\s*(?:[–-]|to)\s*(\d+(?:\.\d+)?)\s*(k|thousand|m|million)?(?!\w)',clean,re.I)
    if m:
        lo=_employee_number((m.group(1) or '')+(m.group(2) or ''))
        hi=_employee_number((m.group(3) or '')+(m.group(4) or ''))
        return _employee_size_band(max(lo,hi))
    return _employee_size_band(_employee_number(clean))


def _explicit_employee_size_display(value):
    """Extract a size band only when prose explicitly talks about company headcount."""
    text=' '.join(str(value or '').split())
    if not text: return ''
    patterns=(
        r'(?P<num>\d[\d,]*(?:\.\d+)?\s*(?:k|thousand|m|million)?)\s*(?:\+\s*)?(?:employees?|staff|headcount|workforce)',
        r'(?:team|staff|workforce)\s+(?:of|with|around|about|approximately|approx\.?|roughly)?\s*(?P<num>\d[\d,]*(?:\.\d+)?\s*(?:k|thousand|m|million)?)\s*(?:people|employees?)?',
    )
    best=0
    for pattern in patterns:
        for m in re.finditer(pattern,text,re.I):
            best=max(best,_employee_number(m.group('num')))
    return _employee_size_band(best)


def _company_registration_evidence(intel, structured=None):
    """Return domain-registration fields recovered from every stored representation.

    Current records keep this data under ``company_intel.structured``.  Older or partially
    normalized records can still contain the same verified evidence in a ``Domain Age`` /
    ``Domain created`` fact or at the company-intel top level.  Dense list rendering should
    not hide an already-known domain year just because one normalization pass omitted the
    structured copy.
    """
    intel=intel if isinstance(intel,dict) else {}
    merged=dict(structured or {}) if isinstance(structured,dict) else {}
    for key in ('domain_age_domain','domain_registered_at','domain_age_years','domain_age_label'):
        if merged.get(key) in (None,'') and intel.get(key) not in (None,''):
            merged[key]=intel.get(key)

    def _domain_from_text(text):
        text=str(text or '').strip()
        m=re.search(r'(?i)\b(?:https?://)?(?:www\.)?([a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+)\b',text)
        return (m.group(1).lower().strip('.') if m else '')

    for fact in (intel.get('facts') or []):
        if not isinstance(fact,dict):
            continue
        label=str(fact.get('label') or '').strip().casefold().replace('_',' ')
        if label not in {'domain age','domain created','domain creation','domain registered','domain registration','domain registration date'}:
            continue
        value=str(fact.get('value') or '').strip()
        if not value:
            continue
        if not merged.get('domain_age_domain'):
            domain=_domain_from_text(value)
            if domain:
                merged['domain_age_domain']=domain
        if not merged.get('domain_registered_at'):
            m=re.search(r'\b((?:18|19|20)\d{2}-\d{2}-\d{2})\b',value)
            if m:
                merged['domain_registered_at']=m.group(1)
            else:
                m=re.search(r'(?i)\b(?:registered|created|creation|since)\D{0,12}((?:18|19|20)\d{2})\b',value)
                if m:
                    merged['domain_registered_at']=m.group(1)
        if merged.get('domain_age_years') in (None,''):
            if re.search(r'(?i)\b<\s*1\s*(?:yr|yrs|year|years)\b',value):
                merged['domain_age_years']=0
            else:
                m=re.search(r'(?i)(?<!\d)(\d{1,3})\s*(?:yr|yrs|year|years)\b',value)
                if m:
                    try: merged['domain_age_years']=max(0,int(m.group(1)))
                    except Exception: pass
        if not merged.get('domain_age_label') and merged.get('domain_age_years') not in (None,''):
            try:
                years=int(merged.get('domain_age_years'))
                merged['domain_age_label']='<1 yr' if years<1 else (f'{years} yr' if years==1 else f'{years} yrs')
            except Exception:
                pass
    return merged


def _company_info_parts(value):
    try:
        intel=value if isinstance(value,dict) else (getattr(value,'company_intel',{}) or {})
    except Exception:
        intel={}
    if not isinstance(intel,dict): intel={}
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    structured=_company_registration_evidence(intel,structured)
    company_guess=''
    try:
        company_guess=str(value.get('company') if isinstance(value,dict) else getattr(value,'company','') or '').strip()
    except Exception:
        company_guess=''
    intel_company=str(intel.get('company') or '').strip()
    fact_company=''
    for fact in (intel.get('facts') or []):
        if isinstance(fact,dict) and str(fact.get('label') or '').strip().casefold()=='company':
            fact_company=str(fact.get('value') or '').strip(); break
    candidates=[company_guess,intel_company,fact_company]
    if any(_platform_company_label(x) for x in candidates if x):
        return '', '', '', '', ''
    # Do not render employee size or company/domain age unless it is attached to a
    # resolved non-platform company identity. Job boards and ATS platforms often expose
    # their own age/size; a blank company should therefore remain a clean '?' badge.
    if not any(str(x or '').strip() and not _platform_company_label(x) for x in candidates):
        return '', '', '', '', ''
    founded=structured.get('founded_year')
    age=str(structured.get('age_range') or '').strip()
    domain_age=str(structured.get('domain_age_label') or '').strip()
    domain_age_domain=str(structured.get('domain_age_domain') or '').strip()
    if domain_age_domain and _platform_host(domain_age_domain):
        domain_age=''; domain_age_domain=''
    domain_registered_at=str(structured.get('domain_registered_at') or '').strip()
    size=_normalize_company_size_display(structured.get('size_range'))
    explicit_sizes=[]
    # Scan both row prose and retained company research. This repairs common stale parses
    # such as a structured 22 beside explicit prose saying 22,000 employees. We still
    # render only a coarse size band, never the exact headcount in dense list views.
    def _walk_employee_text(node, depth=0):
        if depth>4: return
        if isinstance(node,dict):
            for child in node.values(): _walk_employee_text(child,depth+1)
        elif isinstance(node,(list,tuple)):
            for child in node[:80]: _walk_employee_text(child,depth+1)
        elif isinstance(node,str):
            band=_explicit_employee_size_display(node)
            if band: explicit_sizes.append(band)
    for prose in (getattr(value,'company_summary','') if not isinstance(value,dict) else '', getattr(value,'summary','') if not isinstance(value,dict) else '', getattr(value,'match_summary','') if not isinstance(value,dict) else ''):
        band=_explicit_employee_size_display(prose)
        if band: explicit_sizes.append(band)
    _walk_employee_text(intel)
    age_kind='company' if age or founded else ('domain' if domain_age else '')
    if not age and founded:
        try:
            from django.utils import timezone
            years=max(0, timezone.localdate().year-int(founded))
            age='<1 yr' if years<1 else ('1–3 yr' if years<3 else ('3–5 yr' if years<5 else ('5–10 yr' if years<10 else '10+ yr')))
        except Exception: age=''
    for item in (intel.get('facts') or []):
        if not isinstance(item,dict): continue
        label=str(item.get('label') or '').lower(); val=str(item.get('value') or '').strip()
        if 'size' in label or 'employee' in label or 'headcount' in label:
            candidate=_normalize_company_size_display(val)
            if candidate: explicit_sizes.append(candidate)
        if not founded and ('founded' in label or 'established' in label):
            m=re.search(r'\b(18|19|20)\d{2}\b',val)
            if m:
                founded=int(m.group(0)); age_kind='company'
                try:
                    from django.utils import timezone
                    years=max(0, timezone.localdate().year-founded)
                    age='<1 yr' if years<1 else ('1–3 yr' if years<3 else ('3–5 yr' if years<5 else ('5–10 yr' if years<10 else '10+ yr')))
                except Exception: pass
        if not founded and not age and not domain_age and label=='domain age':
            domain_age=val.split('(')[0].strip(); age_kind='domain'
    if explicit_sizes:
        rank={'1–10':1,'10–20':2,'20–50':3,'50–100':4,'100–250':5,'250–500':6,'500–1,000':7,'1,000+':8}
        strongest=max(explicit_sizes,key=lambda x:rank.get(x,0))
        # Explicit headcount wording in stored facts/summary wins over a weaker stale exact extraction.
        if rank.get(strongest,0)>rank.get(size,0): size=strongest
    display_age=age if age else domain_age
    return display_age,size,age_kind,domain_age_domain,domain_registered_at


def _company_info_confidence(value):
    try:
        intel=value if isinstance(value,dict) else (getattr(value,'company_intel',{}) or {})
    except Exception:
        intel={}
    if not isinstance(intel,dict): intel={}
    raw=intel.get('confidence')
    try:
        confidence=max(0,min(100,int(raw or 0)))
    except Exception:
        text=str(raw or '').strip().lower()
        confidence=85 if text=='high' else (60 if text=='medium' else (30 if text=='low' else 0))
    band='high' if confidence>=75 else ('medium' if confidence>=45 else ('low' if confidence>0 else 'none'))
    label='High' if band=='high' else ('Medium' if band=='medium' else ('Low' if band=='low' else 'Unavailable'))
    return confidence,band,label



@register.filter
def company_info_sort_value(value):
    """Numeric usefulness key: large/established/high-confidence company info first."""
    age,size,age_kind,domain_age_domain,domain_registered_at=_company_info_parts(value)
    confidence,_,_=_company_info_confidence(value)
    size_text=str(size or '').replace('–','-').replace(',','').strip()
    nums=[int(x) for x in re.findall(r'\d+',size_text)]
    if '+' in size_text and nums:
        size_upper=max(nums[0]*2,nums[0]+1000)
    elif nums:
        size_upper=max(nums)
    else:
        size_upper=0
    age_text=str(age or '').replace('–','-').lower()
    age_nums=[int(x) for x in re.findall(r'\d+',age_text)]
    company_age=max(age_nums) if age_nums and age_kind!='domain' else 0
    domain_age=0
    raw_date=str(domain_registered_at or '').strip()
    if raw_date:
        m=re.search(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)',raw_date)
        if m:
            try:
                domain_age=max(0,timezone.now().year-int(m.group(1)))
            except Exception:
                domain_age=0
    known=bool(size_upper or company_age or domain_age or confidence)
    if not known:
        return 999999999999
    # Client list sort starts ascending. A negative composite therefore puts the most
    # useful company intelligence first: larger company, then company maturity, domain
    # maturity and research confidence. Reverse click naturally yields the opposite.
    priority=size_upper*1000000 + company_age*10000 + domain_age*100 + int(confidence or 0)
    return -int(priority)


@register.filter
def remote_sort_value(value):
    """Remote ordering: fully remote, remote/conditional, hybrid, on-site, unknown."""
    try:
        facts=getattr(value,'extracted_facts',{}) or {}
        row=facts.get('remote_classification') if isinstance(facts,dict) else {}
        status=str((row or {}).get('status') or 'unknown').strip().lower()
    except Exception:
        status='unknown'
    return {'fully_remote':0,'remote':1,'hybrid':1,'onsite':2,'not_remote':2,'unknown':3}.get(status,3)


def _company_maturity_stage(age, size):
    age_l=str(age or '').lower()
    size_l=str(size or '').replace('-', '–')
    if '<1' in age_l: return 'new'
    if '10+' in age_l or any(x in age_l for x in ('20+', '25+', '50+', '100+')): return 'old'
    if size_l in {'1–10','10–20'}: return 'small'
    if size_l in {'20–50','50–100'}: return 'medium'
    if size_l in {'100–250','250–500','500–1,000','1,000+'}: return 'large'
    if age_l: return 'small'
    if size_l: return 'medium'
    return 'unknown'


def _company_domain_svg():
    # Domain-age fallback is a domain signal, not company maturity. A plain globe is
    # deliberately unambiguous and avoids the old WWW/zig-zag visual clutter.
    return '<svg class="svg-icon company-maturity-icon company-domain-age-icon" viewBox="0 0 24 24" aria-hidden="true" shape-rendering="geometricPrecision"><g fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.2"/><path d="M3.8 12h16.4M12 3.8c2.35 2.55 3.55 5.28 3.55 8.2S14.35 17.65 12 20.2M12 3.8C9.65 6.35 8.45 9.08 8.45 12S9.65 17.65 12 20.2"/></g></svg>'


def _company_domain_mini_svg():
    """Crisp vector globe for the compact domain-created year line."""
    return '<svg class="company-domain-year-mini-globe" viewBox="0 0 16 16" aria-hidden="true" focusable="false" shape-rendering="geometricPrecision"><g fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.75"/><path d="M2.25 8h11.5M8 2.25c1.65 1.75 2.45 3.67 2.45 5.75S9.65 12 8 13.75M8 2.25C6.35 4 5.55 5.92 5.55 8S6.35 12 8 13.75"/></g></svg>'


def _domain_registration_display(structured, domain_registered_at='', domain_age_label=''):
    """Return (created_year, human_age) from exact RDAP data or stored age evidence.

    RDAP dates win. Older profiles may only carry a domain-age number/label; in that case
    the compact UI still needs a creation year, so derive the best calendar-year estimate.
    """
    try:
        from datetime import date
        from django.utils import timezone
        today=timezone.localdate()
    except Exception:
        from datetime import date
        today=date.today()
    raw_date=str(domain_registered_at or (structured.get('domain_registered_at') if isinstance(structured,dict) else '') or '').strip()
    years=None
    created_year=None
    if raw_date:
        try:
            registered=date.fromisoformat(raw_date[:10])
            created_year=registered.year
            years=max(0,today.year-registered.year-((today.month,today.day)<(registered.month,registered.day)))
        except Exception:
            m=re.search(r'\b(18|19|20)\d{2}\b',raw_date)
            if m: created_year=int(m.group(0))
    if years is None and isinstance(structured,dict):
        raw_years=structured.get('domain_age_years')
        if raw_years not in (None,''):
            try: years=max(0,int(float(raw_years)))
            except Exception: years=None
    label=str(domain_age_label or (structured.get('domain_age_label') if isinstance(structured,dict) else '') or '').strip()
    if years is None and label:
        if '<1' in label:
            years=0
        else:
            m=re.search(r'(?<!\d)(\d+)',label)
            if m:
                try: years=max(0,int(m.group(1)))
                except Exception: years=None
    if created_year is None and years is not None:
        created_year=max(1,today.year-years)
    if years is None and created_year:
        years=max(0,today.year-created_year)
    if years is None:
        age_text=''
    elif years < 1:
        age_text='<1 year'
    elif years == 1:
        age_text='1 year'
    else:
        age_text=f'{years} years'
    return (str(created_year) if created_year else ''), age_text



def _company_stage_svg(stage):
    # One compact visual language: building maturity progresses left-to-right while
    # the footprint/window count conveys approximate organization size.
    paths={
        'new':'<path d="M8 20V10l5-3 5 3v10M11 20v-5h4v5M10.5 11.5h1.5M14 11.5h1.5"/><path d="M21 18c0-2.8 1.3-4.6 4-5.4M23.2 10.6c1.7.2 2.8 1.2 3.3 3"/>',
        'small':'<path d="M6 20V8.5l6-3.2 6 3.2V20M9 20v-5h6v5M8.8 10.5h2M13.2 10.5h2M8.8 13h2M13.2 13h2"/><path d="M21 20v-8h5v8M22.5 14h2M22.5 16.5h2"/>',
        'medium':'<path d="M4 20V7l6-3v16M10 20V5.5l7 2.5v12M6.5 9h1.5M6.5 12h1.5M6.5 15h1.5M12.5 9.5h2M12.5 12.5h2M12.5 15.5h2"/><path d="M19 20V10h7v10M21 12.5h3M21 15.5h3"/>',
        'large':'<path d="M2.5 20V8l6-3v15M8.5 20V5l7 2.5V20M15.5 20V9l6-2v13M5 10h1.5M5 13h1.5M5 16h1.5M11 9h2M11 12h2M11 15h2M18 11h1.5M18 14h1.5M18 17h1.5"/><path d="M23 20V11h6v9M25 13.5h2M25 16.5h2"/>',
        'old':'<path d="M3 20h26M5 18.5V9h22v9.5M3.5 9h25L16 3 3.5 9ZM8 11.5v5M12 11.5v5M16 11.5v5M20 11.5v5M24 11.5v5"/><path d="M11 20v-2.5h10V20"/>',
    }
    body=paths.get(stage, paths['small'])
    return f'<svg class="svg-icon company-maturity-icon" viewBox="0 0 32 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.45" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>'



@register.filter
def post_age_provenance_tooltip(value):
    facts=getattr(value,'extracted_facts',{}) or {}
    post=facts.get('post_age') if isinstance(facts,dict) and isinstance(facts.get('post_age'),dict) else {}
    method=str(post.get('post_age_method') or '').strip().lower()
    reason=' '.join(str(post.get('post_age_reason') or post.get('reason') or '').split())
    evidence=post.get('post_age_evidence') if isinstance(post.get('post_age_evidence'),list) else []
    labels={'explicit':'Page content','structured':'Structured metadata','search_index':'Search index','feed':'Feed/API','source_site':'Source site','first_seen':'First seen','crawl':'Crawl/discovery','url':'URL pattern','inferred':'Estimated','guess':'Estimated','unknown':'Unknown'}
    exact_source=' '.join(str(post.get('exact_source') or post.get('source') or '').split())
    if not method and (post.get('posted_date_explicit') or post.get('exact_date') or post.get('researched_date')):
        method='explicit'
    source=exact_source or labels.get(method,method.replace('_',' ').title() if method else 'Unknown')
    winner=evidence[0] if evidence and isinstance(evidence[0],dict) else {}
    if winner:
        source=' '.join(str(winner.get('source') or winner.get('exact_source') or source).split())[:100]
    if not source or source.casefold() in {'unknown','none','null'}:
        acquisition=facts.get('acquisition') if isinstance(facts.get('acquisition'),dict) else {}
        source=' '.join(str(acquisition.get('adapter') or acquisition.get('path') or '').split()) or 'Unknown'
    # Keep the list cell and tooltip consistent: the youngest bucket is approximate and
    # displayed as "< 3 days" for sub-week posts and "~ 1 week" for 7-13 day posts.
    display_age=_freshness_post_age_display_label(value)
    if display_age in {'Age unknown',''}:
        days=opportunity_post_age_sort_days(value)
        display_age=(f'{days} days' if days is not None else 'unknown')
    evidence_text=reason
    for prefix in ('Best available evidence:', 'Best evidence:', 'Evidence:', 'Reason:'):
        if evidence_text.casefold().startswith(prefix.casefold()):
            evidence_text=evidence_text[len(prefix):].strip()
            break
    if not evidence_text and winner:
        evidence_text=' '.join(str(winner.get('evidence') or winner.get('reason') or winner.get('label') or '').split())
    # Schema/datePosted is already implicit in an exact post date and adds no useful
    # context to a user-facing tooltip. Keep richer evidence (page wording, timestamp,
    # feed/search context, etc.) when it actually explains the age determination.
    obvious=re.sub(r'[^a-z0-9]+',' ',evidence_text.casefold()).strip()
    obvious_tokens=set(obvious.split())
    if obvious and obvious_tokens and obvious_tokens.issubset({'jobposting','job','posting','schema','schemaorg','dateposted','date','posted','structured','metadata'}):
        evidence_text=''
    # Show the useful underlying date instead of merely repeating the approximate bucket.
    date_value=getattr(value,'declared_posted_at',None)
    date_heading='Posted on'
    if not date_value:
        date_value=getattr(value,'estimated_first_seen',None)
        date_heading='Estimated posted on'
    if not date_value:
        raw_date=post.get('exact_date') or post.get('researched_date') or post.get('estimated_date')
        if raw_date:
            try:
                from django.utils.dateparse import parse_datetime, parse_date
                parsed=parse_datetime(str(raw_date)) or parse_date(str(raw_date)[:10])
                date_value=parsed
                date_heading='Posted on' if post.get('posted_date_explicit') else 'Estimated posted on'
            except Exception:
                date_value=None
    date_text=''
    if date_value:
        try:
            if hasattr(date_value,'date') and not isinstance(date_value,__import__('datetime').date):
                date_value=date_value.date()
            date_text=date_value.strftime('%d %b %Y')
        except Exception:
            date_text=str(date_value)[:10]
    lines=[f'Post age: {display_age}']
    if date_text:
        lines.append(f'{date_heading}: {date_text}')
    lines.append(f'Source: {source[:120]}')
    if evidence_text:
        lines.append('Evidence: '+evidence_text[:180])
    return '\n'.join(lines)

@register.simple_tag
def company_info_badge(value):
    age,size,age_kind,domain_age_domain,domain_registered_at=_company_info_parts(value)
    confidence,band,confidence_label=_company_info_confidence(value)
    try:
        intel=value if isinstance(value,dict) else (getattr(value,'company_intel',{}) or {})
    except Exception:
        intel={}
    structured=intel.get('structured') if isinstance(intel,dict) and isinstance(intel.get('structured'),dict) else {}
    structured=_company_registration_evidence(intel,structured)
    # Prefer verified registration evidence over a weaker inferred website/domain. This
    # prevents a stale partial match (for example extra.com for Extra Hop) from hiding an
    # already-known extrahop.com registration date.
    evidence_domain=str(structured.get('domain_age_domain') or '').strip()
    if evidence_domain:
        domain_age_domain=evidence_domain
    evidence_registered=str(structured.get('domain_registered_at') or '').strip()
    if evidence_registered:
        domain_registered_at=evidence_registered

    def _tooltip_domain(raw):
        text=str(raw or '').strip()
        if not text:
            return ''
        try:
            parsed=urllib.parse.urlsplit(text if '://' in text else 'https://'+text)
            host=(parsed.hostname or '').lower().strip('.').removeprefix('www.')
        except Exception:
            host=''
        if not host or _platform_host(host):
            return ''
        labels=[x for x in host.split('.') if x]
        if len(labels)>2 and '.'.join(labels[-2:]) in {'co.uk','org.uk','com.au','net.au','co.nz','com.sg','com.my','co.jp','co.in','com.br','com.mx','co.za'}:
            host='.'.join(labels[-3:])
        elif len(labels)>2:
            host='.'.join(labels[-2:])
        return host

    # Domain registration is stored as domain_age_domain after RDAP succeeds, but older
    # and freshly researched records can already know the official site under another
    # structured/fact field.  Tooltip rendering must use that available evidence instead
    # of hiding it until the RDAP maintenance pass has rewritten the record.
    domain=''
    for raw in (
        domain_age_domain, structured.get('domain_age_domain'), structured.get('company_domain'),
        structured.get('domain'), structured.get('company_website'), structured.get('website'),
        intel.get('company_domain') if isinstance(intel,dict) else '',
        intel.get('domain') if isinstance(intel,dict) else '',
        intel.get('company_website') if isinstance(intel,dict) else '',
        intel.get('website') if isinstance(intel,dict) else '',
    ):
        domain=_tooltip_domain(raw)
        if domain:
            break
    if not domain:
        for fact in (intel.get('facts') or []):
            if not isinstance(fact,dict):
                continue
            label=str(fact.get('label') or '').strip().casefold()
            if label in {'domain','website','company website','official website','homepage','home page'}:
                domain=_tooltip_domain(fact.get('value'))
                if domain:
                    break
    if not domain:
        try:
            raw_company=value.get('company') if isinstance(value,dict) else getattr(value,'company','')
        except Exception:
            raw_company=''
        name_key=re.sub(r'[^a-z0-9]+','',clean_company(raw_company or intel.get('company') or '').casefold())
        if len(name_key)>=4:
            scored=[]
            for pos,row in enumerate((intel.get('sources') or [])[:12]):
                if isinstance(row,dict):
                    raw_url=row.get('url'); title=str(row.get('title') or '')
                else:
                    raw_url=row; title=''
                candidate=_tooltip_domain(raw_url)
                if not candidate:
                    continue
                stem=re.sub(r'[^a-z0-9]+','',candidate.split('.')[0].casefold())
                if not stem or not (name_key in stem or stem in name_key):
                    continue
                score=20-pos+(4 if 'official' in title.casefold() else 0)
                scored.append((score,candidate))
            if scored:
                scored.sort(reverse=True); domain=scored[0][1]

    domain_age_label=str(structured.get('domain_age_label') or '').strip()
    domain_created_year,domain_age_tooltip=_domain_registration_display(
        structured, domain_registered_at or structured.get('domain_registered_at'), domain_age_label
    )
    domain_lines=[]
    if domain:
        domain_lines.append(f'Domain: {domain}')
    if domain_created_year:
        created_detail=domain_created_year+(f' ({domain_age_tooltip})' if domain_age_tooltip else '')
        domain_lines.append(f'Domain created: {created_detail}')

    company_name=''
    try:
        company_name=clean_company(value.get('company') if isinstance(value,dict) else getattr(value,'company','') or '')
        if not company_name:
            company_name=clean_company(intel.get('company') or '')
        if not company_name:
            for fact in (intel.get('facts') or []):
                if isinstance(fact,dict) and str(fact.get('label') or '').strip().casefold()=='company':
                    company_name=clean_company(fact.get('value') or '')
                    if company_name: break
    except Exception:
        company_name=''

    if not age and not size:
        # Keep the existing '?' icon. The tooltip can still explain lifecycle state and
        # expose independently resolved domain registration evidence.
        state_label='No verified company yet'
        try:
            state=(value.get('ai_state') if isinstance(value,dict) else getattr(value,'ai_state',{})) or {}
            company_state=state.get('company') if isinstance(state,dict) else {}
            company_state=company_state if isinstance(company_state,dict) else {}
            values=[str(company_state.get(k) or '').lower() for k in ('initial','recovery','last_manual')]
            if 'queued' in values: state_label='Queued'
            elif any(x in {'running','researching'} for x in values): state_label='Researching'
            elif 'failed' in values: state_label='Research failed'
            elif isinstance(intel,dict) and intel.get('status')=='complete': state_label='Unavailable'
        except Exception:
            pass
        # A question mark means there is no useful Company Info to explain yet. Avoid
        # opening an empty/state-only tooltip over dense lists.
        return mark_safe('<span class="company-info-unknown" aria-label="Company Info unavailable">?</span>')

    stage=_company_maturity_stage(age,size)
    details=['Company: '+(company_name or 'Unknown / unresolved')]
    # The tooltip is a single consistent Company Info surface regardless of whether
    # the compact badge uses the building icon (company age/size) or globe icon
    # (domain-age fallback). Only show facts that are actually available.
    if age and age_kind!='domain':
        details.append(f'Company age: {age}')
    if size:
        details.append(f'Company size: {size} employees')
    details.extend(domain_lines)
    details.append(f'Research confidence: {confidence_label}')
    title='\n'.join(details)
    icon=_company_domain_svg() if age_kind=='domain' else _company_stage_svg(stage)
    display_band='none' if age_kind=='domain' else band
    line_parts=[]
    if age_kind=='domain':
        # The globe already means domain-registration evidence. Show the creation year
        # below it rather than another age value such as "14 yrs".
        if domain_created_year:
            line_parts.append(f'<span>{escape(domain_created_year)}</span>')
    else:
        for item in (age,size):
            if item: line_parts.append(f'<span>{escape(item)}</span>')
        # On a normal company/building badge the domain date is supplemental. A tiny
        # inline SVG keeps the signal recognizable and crisp even at this dense size.
        if domain_created_year:
            line_parts.append(
                f'<span class="company-domain-year-line">{_company_domain_mini_svg()}'
                f'<span>{escape(domain_created_year)}</span></span>'
            )
    lines=''.join(line_parts)
    return mark_safe(f'<span class="company-info-stage company-stage-{stage} company-confidence-{display_band} scout-multiline-tooltip" data-tooltip="{escape(title)}" aria-label="{escape(title.replace(chr(10), "; "))}">{icon}<span class="company-info-lines">{lines}</span></span>')

@register.filter
def apply_via_label(opportunity):
    channel=str(getattr(opportunity,'channel','') or '').lower()
    if channel=='ats': return 'ATS'
    if channel=='email': return 'Email'
    if channel=='forum': return 'Forum'
    try:
        if getattr(getattr(opportunity,'source',None),'source_type','') == 'forum': return 'Forum'
    except Exception:
        pass
    facts=getattr(opportunity,'extracted_facts',None) if isinstance(getattr(opportunity,'extracted_facts',None),dict) else {}
    if isinstance(facts.get('forum'),dict) or (facts.get('acquisition') or {}).get('source_category') == 'forum': return 'Forum'
    if channel in {'website','public','community'}: return 'Website / form'
    return 'Email' if getattr(opportunity,'contact_email','') else 'Unknown / Other'

@register.filter
def opportunity_has_applied(opportunity):
    try:
        app=opportunity.application
    except Exception:
        return False
    return bool(getattr(app,'applied_at',None) or str(getattr(app,'status','') or '').lower() in {'applied','reply','interview','rejected','accepted','closed'})

@register.filter
def apply_via_tooltip(opportunity):
    via=apply_via_label(opportunity)
    try: app=opportunity.application
    except Exception: app=None
    applied=bool(app and (getattr(app,'applied_at',None) or str(getattr(app,'status','') or '').lower() in {'applied','reply','interview','rejected','accepted','closed'}))
    if not applied:
        return 'Contact via '+via
    date=getattr(app,'applied_at',None)
    if date:
        try:
            from django.utils import timezone
            return 'Handled via '+via+' · '+timezone.localtime(date).strftime('%d/%m/%Y %H:%M:%S')
        except Exception: pass
    return 'Handled via '+via


@register.filter
def research_value(value, key):
    try:
        facts=value if isinstance(value,dict) else {}
        item=facts.get(key)
        if isinstance(item,dict): return item.get('summary') or item.get('text') or item.get('value') or ''
        return item or ''
    except Exception:
        return ''


_ICONS={
'export':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h8l4 4V20.5H6zM14 3.5v4h4M9 12h6M9 15h6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 9v7M9.5 13.5 12 16l2.5-2.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'copy':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="7" width="11" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M16 7V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h1" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
'open':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5M19 5l-8 8M19 13v6H5V5h6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'external_arrow':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 16 18 6M11 6h7v7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'actions':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="19" cy="12" r="1.6" fill="currentColor"/></svg>',
'note':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4.5h14v12H9l-4 3zM8 8h8M8 11.5h6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'repeat_search':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h12M13 7l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'details':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h10l4 4v12H5zM15 4v5h4M8 13h5M8 16h7" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><circle cx="16.8" cy="12.2" r="2.2" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
'search':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M15.5 15.5L21 21" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'apply':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19l14-14M10 5h9v9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'review':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>',
'info':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 10v6M12 7h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
'raw':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
'blacklist':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M6 18L18 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'blocked_domain':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 19 6v5.3c0 4.4-2.6 7.5-7 9.2-4.4-1.7-7-4.8-7-9.2V6z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M7.8 16.2 16.3 7.7" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>',
'application_type':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h8l4 4V20H6zM14 3.5v4h4M9 12h6M9 15h4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="m9 18 1.5 1.5L14 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'outreach_type':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 11.5 20 4l-5.5 16-3-6.5zM11.5 13.5 20 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'lead_type':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M3.5 19c.8-3.5 3-5.3 5.5-5.3s4.7 1.8 5.5 5.3M15.5 8.5h5M18 6v5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
'campaign_type':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v14H5zM8 9h8M8 13h6M8 17h4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'opportunity_type':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7V5h10v2M5 8h14v11H5zM9 12h6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'scope_all':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 8h8v8h-8zM13.5 8h7v8h-7M7.5 5v3M17 5v3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
}

@register.simple_tag
def icon(name):
    return mark_safe(_ICONS.get(name,''))

@register.filter
def language_flag(code):
    c=(code or '').strip().lower().replace('_','-').split('-',1)[0]
    mapping={'en':'GB','ko':'KR','ja':'JP','zh':'CN','de':'DE','fr':'FR','es':'ES','pt':'PT','it':'IT','ru':'RU','nl':'NL','pl':'PL','sv':'SE','no':'NO','da':'DK','fi':'FI','cs':'CZ','tr':'TR','vi':'VN','th':'TH','id':'ID','ms':'MY'}
    cc=mapping.get(c,'')
    return ''.join(chr(127397+ord(x)) for x in cc) if cc else ''

@register.filter
def language_name(code):
    c=(code or '').strip().lower().replace('_','-').split('-',1)[0]
    return {'en':'English','ko':'Korean','ja':'Japanese','zh':'Chinese','de':'German','fr':'French','es':'Spanish','pt':'Portuguese','it':'Italian','ru':'Russian','nl':'Dutch','pl':'Polish','sv':'Swedish','no':'Norwegian','da':'Danish','fi':'Finnish','cs':'Czech','tr':'Turkish','vi':'Vietnamese','th':'Thai','id':'Indonesian','ms':'Malay'}.get(c,c.upper() if c else 'Unknown')

# Add semantic icons without relying on font/Unicode glyph rendering.
_ICONS.update({
'fresh':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 14c5-8 12-8 14-8-1 7-4 12-10 12-3 0-5-1-5-1s2-4 7-6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'clock':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 7v5l3.5 2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'archive':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16v13H4zM3 4h18v3H3zM9 11h6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
'evergreen':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 4.5C12.2 4.7 6.8 8 5.2 13.2c-.8 2.6.4 5.1 2.7 5.8 2.7.8 5.5-.6 7.2-3.3 1.9-3 2.9-6.7 4.4-11.2Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M5.5 19.5c2.1-3.7 5.2-6.6 9.5-8.9" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
'fit':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>',
'reevaluate':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 7.5A8 8 0 1 0 20 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M19 3.5v4.7h-4.7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="m9.1 12 1.8 1.8 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'web':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M3 12h18M12 3c2.5 2.6 3.7 5.6 3.7 9S14.5 18.4 12 21M12 3C9.5 5.6 8.3 8.6 8.3 12S9.5 18.4 12 21" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>',
'email':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M4 7l8 6 8-6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
'email_outgoing':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5 11 13l5.2-3.6M3 7.5v10.3c0 .7.5 1.2 1.2 1.2H15" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M3.5 6h12.3c.7 0 1.2.5 1.2 1.2V9M15 15h6m0 0-2.5-2.5M21 15l-2.5 2.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'company':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V7h7v13M11 20V4h9v16M7 10h1M7 13h1M7 16h1M14 8h1M17 8h1M14 11h1M17 11h1M14 14h1M17 14h1" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'delete':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M9 7V4h6v3M8 10v8M12 10v8M16 10v8M7 7l1 14h8l1-14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
'restore':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 8V4m0 0h4M5 4l3 3a8 8 0 1 1-2.2 8.2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'show_deleted':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16v13H4zM3 4h18v3H3z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M8 13c1.2-1.6 2.6-2.4 4-2.4s2.8.8 4 2.4c-1.2 1.6-2.6 2.4-4 2.4S9.2 14.6 8 13Z" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="12" cy="13" r="1.2" fill="currentColor"/></svg>',
'hide_deleted':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16v13H4zM3 4h18v3H3z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M7.5 13c1.3-1.6 2.8-2.4 4.5-2.4 1.5 0 2.9.7 4.1 2.1M9.4 15.1c.8.3 1.7.5 2.6.5 1.7 0 3.2-.8 4.5-2.4M7 9l10 8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
'empty':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M9 7V4h6v3M7 7l1 14h8l1-14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="m10 11 4 4m0-4-4 4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
'sweep':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15.5 3.5 20 8l-7.2 7.2-4.5-4.5z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M8.3 10.7 4.2 14.8c-1.7 1.7-.8 4.7 1.6 5.1 3.7.6 7.1-.2 10.2-2.5l-3.2-3.2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M4.8 17.1c2.7.7 5.3.3 7.7-1" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',

'edit':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19h3.5L19 8.5 15.5 5 5 15.5zM13.8 6.7l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'next':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M14 7l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'refresh':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 7V3l-2.1 2.1A8 8 0 1 0 20 12" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'save':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h12l2 2v14H5zM8 4v6h8V4M8 20v-6h8v6" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linejoin="round"/></svg>',
'filter':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16l-6.5 7v5.5l-3 1.5v-7z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
'check':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5 9.5 17 19 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'close':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'play':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5 18 12 8 18.5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
'pause':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 6v12M16 6v12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
'running_state':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13h3l2-6 3 11 2.5-8 1.5 3H20" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'paused_state':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 6v12M15.5 6v12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
'status_state':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M12 5v14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'campaign_add':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5.5 20V4.5M6 5h9l-1.8 3.5L15 12H6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M17.5 15v5M15 17.5h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'template_add':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3.5h9l4 4V20H5zM14 3.5v4h4M8 11h5M8 14h4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M17.5 14.5v5M15 17h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'reset_defaults':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8V4m0 0h4M6 4l2.8 2.8A7.5 7.5 0 1 1 5 13" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 11h6M9 14h4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
'imap_sync':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16v11H4zM5 7l7 5 7-5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M7 20h5M7 20l1.8-1.8M17 4h-5M17 4l-1.8 1.8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'history_import':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5a7 7 0 1 1-6.2 3.8M5 5v4h4M12 8v4l2.5 1.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M18.5 15v5M16 17.5l2.5 2.5 2.5-2.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'sort_up_small':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 15 5-5 5 5" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'sort_down_small':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 9 5 5 5-5" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>',
})




@register.filter
def fit_level(value):
    """Map ScoutBox's internal 0-100 fit score to the nearest 0-5 user level."""
    try:
        score=max(0,min(100,int(value or 0)))
    except Exception:
        score=0
    return max(0,min(5,(score+10)//20))

@register.filter
def truncatechars_word(value, arg):
    """Character-limit preview without cutting the final displayed word in half."""
    text=str(value or '')
    try:
        limit=max(1,int(arg))
    except Exception:
        return text
    if len(text) <= limit:
        return text
    if limit <= 1:
        return '…'
    budget=limit-1
    fragment=text[:budget]
    # If the next character continues the current token, remove that whole token.
    if budget < len(text) and not text[budget].isspace() and fragment and not fragment[-1].isspace():
        cut=max(fragment.rfind(' '), fragment.rfind('\t'), fragment.rfind('\n'))
        if cut > 0:
            fragment=fragment[:cut]
    fragment=fragment.rstrip(' ,;:/|-')
    return (fragment or text[:budget].rstrip())+'…'

@register.filter
def truncatechars_keyword(value, arg):
    """Character-limit preview that never cuts a comma/semicolon-delimited keyword in half."""
    text=str(value or '')
    try:
        limit=max(1,int(arg))
    except Exception:
        return text
    if len(text) <= limit:
        return text
    if limit <= 1:
        return '…'
    budget=limit-1
    fragment=text[:budget]
    separators=',;|\n'
    # If the boundary lands exactly after a complete keyword, keep it. Otherwise
    # step back to the previous keyword separator instead of cutting a keyword.
    next_char=text[budget:budget+1]
    if next_char not in separators:
        cut=max(fragment.rfind(','), fragment.rfind(';'), fragment.rfind('|'), fragment.rfind('\n'))
        if cut > 0:
            fragment=fragment[:cut]
        else:
            # Non-list text still gets a readable fallback rather than a mid-word cut.
            cut=max(fragment.rfind(' '), fragment.rfind('\t'))
            if cut > 0:
                fragment=fragment[:cut]
    fragment=fragment.rstrip(' ,;|\t\r\n')
    return (fragment or text[:budget].rstrip())+'…'

@register.filter
def strip_reason_prefix(value):
    text=re.sub(r'(?is)^\s*(?:#{1,6}\s*)?reason\s*:\s*', '', str(value or '')).strip()
    # Internal Cloud pipeline provenance is useful in diagnostics, not in normal review UI.
    text=re.sub(r'(?is)\bGrounded cloud research candidate; deterministic ScoutBox policy checks applied\.?\s*', '', text).strip()
    return text

@register.filter
def simple_raw_content(value):
    return mark_safe(simple_job_html(value))

@register.filter
def titlecase_token(value):
    return ' '.join(part.capitalize() if part else part for part in str(value or '').split())

@register.simple_tag
def source_icon(source_name='', channel=''):
    name=str(source_name or '').lower(); ch=str(channel or '').lower()
    if 'github' in name: key='source_code'; cls='code'
    elif ch=='forum' or 'forum' in name or 'community forum' in name: key='forum'; cls='forum'
    elif 'linkedin' in name or 'indeed' in name or 'glassdoor' in name: key='source_jobs'; cls='jobs'
    elif any(x in name for x in ('google','bing','duckduckgo','brave','yahoo','search')): key='source_search'; cls='search'
    elif any(x in name for x in ('facebook','reddit','twitter','x.com','social')) or ch=='community': key='source_social'; cls='social'
    elif ch=='email': key='email'; cls='email'
    elif ch in ('ats','website'): key='source_direct'; cls='direct'
    else: key='web'; cls='web'
    return mark_safe(f'<span class="source-kind-icon {cls}" aria-hidden="true">{_ICONS.get(key,_ICONS.get("web",""))}</span>')


_ICONS.update({
'source_search':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="m15 15 5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'source_code':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'source_jobs':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="7" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M9 7V5h6v2M3 11h18M10 11v2h4v-2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
'source_social':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="12" r="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="18" cy="7" r="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="18" cy="17" r="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="m8.3 10.9 7.4-2.8M8.3 13.1l7.4 2.8" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>',
'source_direct':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h14M14 7l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>'
})

_ICONS.update({
'runtime_local':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M8 21h8M12 17v4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
'runtime_cloud':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 18h11a4 4 0 0 0 .5-8 6.2 6.2 0 0 0-11.8-1.4A4.7 4.7 0 0 0 7 18Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>'
})

_ICONS.update({
'read_all':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14M5 12h14M5 18h14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'read_unread':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14v10H5z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M8 11h8M8 14h5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
'read_seen':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 12c2.2-3.5 5-5.2 8.5-5.2s6.3 1.7 8.5 5.2c-2.2 3.5-5 5.2-8.5 5.2S5.7 15.5 3.5 12Z" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="2.3" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>',
'mark_state':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h10l4 4v10H5z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="m8 13 2.3 2.3L16 9.8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
})

_ICONS.update({
'provider_idle_ready_v3':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14M5 11h10M5 16h7M5 20h4" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>',
'quota_info_v1':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 10v9M12 5h.01" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>',
'quota_details_v2':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h3M11 7h8M5 12h3M11 12h8M5 17h3M11 17h8" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>',
'provider_no_results_v3':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16l-6 7v4l-4 2v-6zM16.5 16.5 21 21M21 16.5 16.5 21" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'provider_ok_v3':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 12.5 9.2 17 19.5 6.8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'provider_warn_v3':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v12M12 20h.01" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg>',
'quota_ok_v3':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 17a8 8 0 0 1 16 0M12 17l4-5M7 17h.01M17 17h.01" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'ai_queued_v1':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h10M7 21h10M8 4c0 4 2 5 4 7-2 2-4 3-4 7M16 4c0 4-2 5-4 7 2 2 4 3 4 7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'provider_error_v3':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5.5 5.5 18.5 18.5M18.5 5.5 5.5 18.5" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/></svg>',
'ai_recovered_v2':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="m8.3 12.2 2.4 2.4 5-5.2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'ai_malformed_v2':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.8 21 19.5H3L12 3.8Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 9v5.2M12 17.5h.01" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/></svg>'
})




_ICONS.update({'tracking_load':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 12h11M11.5 7.5 16 12l-4.5 4.5M18.5 5.5h1.5v13h-1.5" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>'})
_ICONS.update({'calendar':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5.5" width="17" height="15" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M7.5 3.5v4M16.5 3.5v4M3.5 9.5h17" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M7 13h2M11 13h2M15 13h2M7 17h2M11 17h2" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>'})
_ICONS.update({'database':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="7" ry="2.8" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5 5.5v6c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8v-6M5 11.5v6c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8v-6" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>'})
_ICONS.update({'redis':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 8 4-8 4-8-4 8-4Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="m4 11 8 4 8-4M4 15l8 4 8-4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><circle cx="17.6" cy="7" r="1" fill="currentColor"/></svg>'})
_ICONS.update({'external_statistics':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3.5" width="18" height="17" rx="3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6.5 8h11M6.5 12h11M6.5 16h11" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round"/><circle cx="10" cy="8" r="1.55" fill="currentColor"/><circle cx="15" cy="12" r="1.55" fill="currentColor"/><circle cx="8.5" cy="16" r="1.55" fill="currentColor"/></svg>'})

_ICONS.update({'link':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9.5 14.5l5-5M7.5 17.5l-1 1a3.5 3.5 0 0 1-5-5l4-4a3.5 3.5 0 0 1 5 0M16.5 6.5l1-1a3.5 3.5 0 0 1 5 5l-4 4a3.5 3.5 0 0 1-5 0" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'})
_ICONS.update({'word':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h8l4 4V20.5H6zM14 3.5v4h4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M8.3 11.2 9.8 17l2.2-4.5 2.2 4.5 1.5-5.8" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round"/></svg>'})
_ICONS.update({'folder_detect':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 7h6l1.8 2H20.5v9.5H3.5z" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linejoin="round"/><path d="m8 14 2.1 2.1L15.5 11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="18.2" cy="7.2" r="1.2" fill="currentColor"/></svg>'})
_ICONS.update({'stop':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="1" fill="currentColor"/></svg>'})

_ICONS.update({'status_details':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M8 9h8M8 12h8M8 15h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'})

_ICONS.update({
'workflow':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h7M13 6h7M8 6v6h8v6M4 18h5M15 18h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="6" r="1.8" fill="currentColor"/><circle cx="12" cy="18" r="1.8" fill="currentColor"/></svg>',
'architecture':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h6v5H4zM14 5h6v5h-6zM9 15h6v5H9zM7 10v2.5h5M17 10v2.5h-5M12 12.5V15" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"/></svg>',
'terminal':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="m7 9 3 3-3 3M12.5 15H17" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'history_add':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5a7 7 0 1 1-6.2 3.8M5 5v4h4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 9v6M9 12h6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
'dashboard':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13a8 8 0 1 1 16 0v6H4zM12 13l4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="13" r="1.5" fill="currentColor"/></svg>',
'error':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11M12 19h.01" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
'reply':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 7 4 12l6 5v-3c5 0 8 1 10 4-1-6-4-9-10-9z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
'step1':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 9l3-3v12M8 18h8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'step2':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 9c.2-2 1.7-3 4-3 2.5 0 4 1.2 4 3 0 2.2-1.8 3.4-4.2 5C9.7 15.4 8 16.5 8 18h8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'step3':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 7c.8-.7 2-1 3.5-1 2.5 0 4 1.1 4 3 0 1.6-1.2 2.6-3.2 2.9 2.2.2 3.7 1.2 3.7 3 0 2.1-1.7 3.4-4.5 3.4-1.6 0-2.9-.4-3.8-1.2M10 12h2.8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'step4':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 18V6L8 15h10M15 11v7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'step5':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 6H9l-.8 5h3.7c2.7 0 4.3 1.3 4.3 3.5S14.5 18 11.8 18c-1.7 0-3-.4-4-1.2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
'step6':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15.8 7.2C15 6.4 13.8 6 12.4 6 9.4 6 7.7 8.4 7.7 12.4c0 3.7 1.5 5.8 4.4 5.8 2.5 0 4.1-1.4 4.1-3.5s-1.5-3.3-3.8-3.3c-2 0-3.5 1-4.3 2.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
})

@register.filter
def domain_name(value):
    try:
        host=urllib.parse.urlparse(str(value or '')).netloc.lower().split('@')[-1].split(':')[0].removeprefix('www.')
    except Exception:
        host=''
    return host

@register.filter
def blacklist_review_domain(value, company=''):
    try:
        return _blacklist_review_domain(value, company)
    except Exception:
        return ''

@register.filter
def blacklist_review_domain_for_record(value):
    try:
        return _blacklist_review_domain_for_record(value)
    except Exception:
        return ''

@register.filter
def blacklist_company_valid_for_record(value):
    try:
        return bool(_company_blacklist_candidate(value).get('valid'))
    except Exception:
        return False

@register.filter
def blacklist_company_invalid_reason(value):
    try:
        return str(_company_blacklist_candidate(value).get('reason') or '')
    except Exception:
        return 'No usable company name.'


@register.filter
def record_locations_display(value):
    try:
        return _record_location_display(value, limit=4)
    except Exception:
        return ''

@register.filter
def record_locations_icon(value):
    try:
        labels=[x.get('label') for x in _record_location_items(value) if x.get('label')]
        if len(labels) > 1:
            return '◇'
        if labels:
            return location_icon(labels[0]) or country_flag(labels[0])
    except Exception:
        pass
    return ''

@register.filter
def record_locations_title(value):
    try:
        return _record_location_title(value)
    except Exception:
        return ''

@register.filter
def hidden_lead_blacklist_valid_for_record(value):
    try:
        from portal.services.blacklist import blacklist_candidate_for_record
        return bool(blacklist_candidate_for_record(value, allow_domain_only=True).get('valid'))
    except Exception:
        return False

@register.filter
def hidden_lead_blacklist_invalid_reason(value):
    try:
        from portal.services.blacklist import blacklist_candidate_for_record
        return str(blacklist_candidate_for_record(value, allow_domain_only=True).get('reason') or '')
    except Exception:
        return 'No usable company name or safe domain.'

@register.filter
def compact_url(value):
    """Display a URL without scheme/www while leaving the real href untouched."""
    raw=str(value or '').strip()
    if not raw:
        return ''
    try:
        parsed=urllib.parse.urlsplit(raw if '://' in raw else 'https://'+raw)
        host=(parsed.netloc or '').split('@')[-1].removeprefix('www.')
        path=parsed.path or ''
        query=('?'+parsed.query) if parsed.query else ''
        label=(host+path+query).rstrip('/') or host
        return label
    except Exception:
        return re.sub(r'(?i)^https?://(?:www\.)?', '', raw).rstrip('/')

@register.simple_tag
def public_search_url(provider, query):
    """Public browser-search URL matching Search Activity's repeat-search action."""
    q=str(query or '').strip()
    if not q: return ''
    name=str(provider or '').strip().lower()
    if 'naver' in name: return 'https://search.naver.com/search.naver?'+urllib.parse.urlencode({'query':q})
    if 'yandex' in name: return 'https://yandex.com/search/?'+urllib.parse.urlencode({'text':q})
    if 'yahoo' in name: return 'https://search.yahoo.com/search?'+urllib.parse.urlencode({'p':q})
    if 'startpage' in name: return 'https://www.startpage.com/sp/search?'+urllib.parse.urlencode({'query':q})
    if 'brave' in name: return 'https://search.brave.com/search?'+urllib.parse.urlencode({'q':q})
    if 'duck' in name: return 'https://duckduckgo.com/?'+urllib.parse.urlencode({'q':q})
    if 'bing' in name: return 'https://www.bing.com/search?'+urllib.parse.urlencode({'q':q})
    if 'ecosia' in name: return 'https://www.ecosia.org/search?'+urllib.parse.urlencode({'q':q})
    if 'mojeek' in name: return 'https://www.mojeek.com/search?'+urllib.parse.urlencode({'q':q})
    if 'baidu' in name: return 'https://www.baidu.com/s?'+urllib.parse.urlencode({'wd':q})
    return 'https://www.google.com/search?'+urllib.parse.urlencode({'q':q})

@register.filter
def domain_home_url(value):
    """Return the site's homepage for a URL while keeping the displayed domain separate."""
    try:
        parsed=urllib.parse.urlparse(str(value or '').strip())
        host=(parsed.netloc or '').split('@')[-1]
        if not host:
            return ''
        scheme=parsed.scheme if parsed.scheme in ('http','https') else 'https'
        return f'{scheme}://{host}/'
    except Exception:
        return ''

@register.filter
def email_domain_home_url(value):
    """Return an HTTPS homepage derived from the domain portion of an email address."""
    try:
        raw=str(value or '').strip()
        if '@' not in raw:
            return ''
        host=raw.rsplit('@',1)[1].strip().strip('.').lower()
        if not host or '/' in host or ':' in host or ' ' in host or '.' not in host:
            return ''
        return f'https://{host}/'
    except Exception:
        return ''

@register.simple_tag
def remote_signal(opportunity):
    facts=getattr(opportunity,'extracted_facts',{}) or {}
    row=facts.get('remote_classification') or {}
    status=str(row.get('status') or 'unknown').strip().lower()
    labels={'fully_remote':'Fully remote','remote':'Remote','hybrid':'Hybrid','onsite':'On-site','unknown':'Unknown'}
    symbols={
        'fully_remote':'<svg class="remote-check-svg" viewBox="0 0 32 18" aria-hidden="true"><path d="M2 9l4 4 7-9M14 9l4 4 10-11"/></svg>',
        'remote':'<svg class="remote-check-svg single" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 9l4 4 10-11"/></svg>',
        'hybrid':'<svg class="remote-check-svg single" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 9l4 4 10-11"/></svg>',
        'onsite':'<svg class="remote-check-svg single remote-cross-svg" viewBox="0 0 18 18" aria-hidden="true"><path d="M4 4l10 10M14 4 4 14"/></svg>',
        'unknown':'?'
    }
    css={'fully_remote':'confirmed','remote':'remote','hybrid':'remote','onsite':'not-remote','unknown':'unknown'}
    if status not in labels: status='unknown'
    raw_label=' '.join(str(row.get('label') or labels[status]).split()) or labels[status]
    # Cloud/local model payloads sometimes persist the machine enum itself as the label
    # (for example ``fully_remote``). Keep the structured status untouched, but never
    # leak that internal token into the dense Opportunity list.
    machine_label=raw_label.casefold().replace('-', '_').replace(' ', '_')
    if machine_label in labels:
        raw_label=labels[status]
    label='Hybrid' if status=='hybrid' else raw_label[:60].rstrip()
    try: confidence=max(0,min(100,int(row.get('confidence') or 0)))
    except Exception: confidence=0
    reason=' '.join(str(row.get('reason') or '').split())
    tooltip_lines=[f'Remote: {label}']
    if confidence:
        tooltip_lines.append(f'Confidence: {confidence}%')
    if reason:
        tooltip_lines.append(f'Reason: {reason[:240]}')
    title='\n'.join(tooltip_lines)
    # Unknown is intentionally just the standard question mark; the repeated
    # "Unknown" caption added visual noise in the dense Opportunity table.
    caption='' if status=='unknown' else f'<small>{escape(label)}</small>'
    if status=='unknown':
        return mark_safe('<span class="remote-status-display unknown" aria-label="Remote status unavailable"><span class="remote-signal remote-mark">?</span></span>')
    return mark_safe(
        f'<span class="remote-status-display {css[status]} scout-multiline-tooltip" data-tooltip="{escape(title)}" '
        f'aria-label="{escape(title.replace(chr(10), "; "))}">'
        f'<span class="remote-signal remote-mark">{symbols[status]}</span>{caption}</span>'
    )

@register.filter
def age_confidence_class(value):
    try: n=int(value or 0)
    except Exception: n=0
    if n>=80: return 'age-confidence-high'
    if n>=55: return 'age-confidence-medium'
    if n>0: return 'age-confidence-low'
    return 'age-confidence-unknown'

@register.simple_tag
def model_stage_field(status_map, stage, field, default=''):
    try:
        return ((status_map or {}).get(stage) or {}).get(field, default)
    except Exception:
        return default

@register.filter
def pipeline_stage_label(stage):
    labels={
        'url_scrape':'URL discovery',
        'jd_analysis':'JD analysis',
        'first_filter':'First filter',
        'company_enrichment':'Company enrichment',
        'freshness':'Freshness',
        'page_summarization':'Page summarization',
        'cv_tailoring':'Resume tailoring',
        'email_draft':'Email draft',
        'question_answers':'Application questions',
        'cold_contact':'Cold contact',
        'import_inference':'Import inference',
    }
    return labels.get(str(stage or ''),str(stage or '').replace('_',' ').title())

@register.filter
def pagination_window(page_obj):
    """Compact, consistent page-number window used by server-paginated list views."""
    try:
        current=int(page_obj.number); total=int(page_obj.paginator.num_pages)
    except Exception:
        return []
    if total <= 1:
        return [1] if total == 1 else []
    keep={1,total}
    keep.update(range(max(1,current-2),min(total,current+2)+1))
    if current <= 4:
        keep.update(range(1,min(total,7)+1))
    if current >= total-3:
        keep.update(range(max(1,total-6),total+1))
    ordered=sorted(keep)
    out=[]; previous=None
    for value in ordered:
        if previous is not None and value-previous>1:
            out.append('…')
        out.append(value); previous=value
    return out

def _compact_filter_params(request):
    token=str(getattr(request,'scoutbox_filter_state_token','') or '').strip()
    if token:
        from django.http import QueryDict
        params=QueryDict('',mutable=True); params['fs']=token
        return params
    return request.GET.copy()


@register.simple_tag
def page_url(request, page_number):
    try:
        params=_compact_filter_params(request)
        params['page']=str(page_number)
        query=params.urlencode()
        return '?' + query if query else '?page='+str(page_number)
    except Exception:
        return '?page='+str(page_number)


@register.simple_tag
def fit_sort_url(request, current_sort=''):
    """Preserve list filters while toggling the server-side Fit ordering."""
    try:
        params=_compact_filter_params(request)
        current=str(current_sort or '').strip().lower()
        params['sort']='fit_asc' if current=='fit_desc' else 'fit_desc'
        params.pop('page',None)
        query=params.urlencode()
        return '?' + query if query else '?sort=fit_desc'
    except Exception:
        return '?sort=fit_desc'


@register.simple_tag
def post_age_sort_url(request, current_sort=''):
    """Preserve filters while toggling full-result Post Age ordering."""
    try:
        params=_compact_filter_params(request)
        current=str(current_sort or '').strip().lower()
        params['sort']='age_desc' if current=='age_asc' else 'age_asc'
        params.pop('page',None)
        query=params.urlencode()
        return '?' + query if query else '?sort=age_asc'
    except Exception:
        return '?sort=age_asc'


@register.simple_tag
def server_sort_url(request, current_sort, ascending_mode, descending_mode, default_direction='asc'):
    """Preserve current list filters while toggling a server-side sort mode.

    Server-paginated lists must sort the complete filtered result set before pagination.
    This helper keeps that behavior consistent without hand-building query strings in
    each template. ``default_direction`` controls the first click when the column is not
    currently active.
    """
    try:
        params=_compact_filter_params(request)
        current=str(current_sort or '').strip().lower()
        asc=str(ascending_mode or '').strip().lower()
        desc=str(descending_mode or '').strip().lower()
        default=str(default_direction or 'asc').strip().lower()
        if current==asc:
            target=desc
        elif current==desc:
            target=asc
        else:
            target=desc if default=='desc' else asc
        params['sort']=target
        params.pop('page',None)
        query=params.urlencode()
        return '?' + query if query else '?sort='+target
    except Exception:
        target=str(descending_mode if str(default_direction).strip().lower()=='desc' else ascending_mode)
        return '?sort='+target

_ICONS.update({'forum':'<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5h11.2a3 3 0 0 1 3 3v4.8a3 3 0 0 1-3 3H9.2L5.4 19v-2.7H4a3 3 0 0 1-3-3V8.5a3 3 0 0 1 3-3Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M8.8 7.8h7.2a3 3 0 0 1 3 3v4.2l2 1.5v-2.7a3 3 0 0 0 2-2.8V10a3 3 0 0 0-3-3H10.2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M5.5 9.5h8M5.5 12.5h6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'})

@register.filter
def reassessment_display_message(value):
    """Return the useful reassessment status text without duplicated leading progress."""
    text=' '.join(str(value or '').split()).strip()
    text=re.sub(r'^\d+\s*%\s*[·:;-]\s*', '', text)
    text=re.sub(r'^(?:Work\s+in\s+progress|Queued)\s*[·:;-]\s*', '', text, flags=re.I)
    return text
