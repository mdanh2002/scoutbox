from __future__ import annotations

import re
import json
from datetime import datetime, timedelta
from django.utils import timezone

# Conservative phrases that indicate a HTTP-200 shell no longer represents an active
# opportunity. Keep these deterministic so URL-health and discovery agree even if AI is off.
_SOFT_MISSING_PATTERNS = [
    (r'\bapplications?(?:\s+for\s+(?:this|the)\s+(?:job|position|vacancy|role|opportunity))?\s+(?:are\s+)?(?:now\s+)?closed\b', 'applications are closed'),
    (r'\bapplications?\s+(?:have\s+)?closed\b', 'applications have closed'),
    (r'\b(?:we(?:\'re|\s+are)\s+)?no\s+longer\s+accepting\s+(?:applications?|applicants?)\b', 'no longer accepting applicants'),
    (r'\b(?:not|no\s+longer)\s+(?:open\s+for|accepting)\s+(?:applications?|applicants?)\b', 'not accepting applicants'),
    (r'\b(?:job|position|vacancy|role|opportunity|requisition|posting)\s+(?:is\s+|has\s+been\s+|was\s+)?(?:closed|filled|expired|removed|cancelled|canceled)\b', 'job is closed or filled'),
    (r'\b(?:this\s+)?(?:job|position|vacancy|role|opportunity|requisition|posting)\s+(?:is\s+|has\s+been\s+)?no\s+longer\s+(?:available|active|open|accepting\s+applications?)\b', 'job is no longer available'),
    (r'\b(?:job|position|vacancy|role|opportunity|requisition|posting)\s+(?:could\s+not\s+be|was\s+not|not)\s+found\b', 'job not found'),
    (r'\b(?:the\s+)?(?:requested\s+)?(?:job|position|vacancy|role|opportunity|requisition|posting)\s+(?:does\s+not|doesn\'t)\s+exist\b', 'job not found'),
    (r'\bpage\s+not\s+found\b|\b404\s+(?:error|not\s+found)\b', 'page not found'),
    (r'\bthis\s+(?:page|listing|content)\s+(?:is\s+)?not\s+(?:a\s+)?(?:job|vacancy|career)\s+(?:post|posting|listing|opportunity)\b', 'not a job post'),
    (r'\bthis\s+job\s+posting\s+has\s+(?:been\s+)?removed\b', 'job posting removed'),
    (r'\bthe\s+(?:job\s+)?posting\s+you\s+are\s+looking\s+for\s+(?:is\s+)?(?:no\s+longer\s+available|not\s+available)\b', 'posting no longer available'),
    (r'\b(?:this\s+)?(?:vacancy|role|position)\s+(?:is\s+)?(?:not\s+available|no\s+longer\s+available)\b', 'job is no longer available'),
]

# Script ranges which are usually stray search-engine/site suffixes in an otherwise English
# role title. Latin accented characters are intentionally retained.
_FOREIGN_SCRIPT_RE = re.compile(
    r'[\u1100-\u11ff\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af'
    r'\u0400-\u052f\u0600-\u06ff\u0750-\u077f\u0e00-\u0e7f\u1780-\u17ff]+'
)
_LATIN_ROLE_RE = re.compile(r'[A-Za-z]{2,}')
_ROLE_WORD_RE = re.compile(r'(?i)\b(engineer|developer|consultant|architect|writer|technical|firmware|software|linux|embedded|systems?|principal|specialist|manager|director|lead|scientist|researcher|designer|devops|security|platform|kernel|administrator|analyst|programmer)\b')

_COUNTRY_ALIASES = {
    'us': 'United States', 'u.s.': 'United States', 'u.s.a.': 'United States', 'usa': 'United States',
    'united states of america': 'United States', 'uk': 'United Kingdom', 'u.k.': 'United Kingdom',
    'gb': 'United Kingdom', 'great britain': 'United Kingdom', 'britain': 'United Kingdom',
    'republic of korea': 'South Korea', 'korea, republic of': 'South Korea', 'uae': 'United Arab Emirates',
}
# Most common country names first. Generic handling in templates can still recognize the
# complete country list; this parser is intentionally focused on remote-restriction evidence.
_COUNTRY_NAMES = [
    'United States','United Kingdom','Poland','Germany','France','Spain','Portugal','Italy','Netherlands',
    'Belgium','Switzerland','Austria','Sweden','Norway','Denmark','Finland','Ireland','Canada','Mexico',
    'Brazil','Argentina','Chile','Colombia','Australia','New Zealand','Singapore','India','Japan','China',
    'South Korea','Taiwan','Hong Kong','Malaysia','Indonesia','Philippines','Thailand','Vietnam','Israel',
    'United Arab Emirates','Saudi Arabia','South Africa','Czechia','Czech Republic','Slovakia','Hungary',
    'Romania','Bulgaria','Greece','Croatia','Serbia','Slovenia','Estonia','Latvia','Lithuania','Ukraine',
]




_ADULT_CONTENT_PATTERNS = [
    r"\b(?:porn|pornographic|xxx|hardcore|explicit sex|sex video|adult video|adult content|adult entertainment|nude(?:s| photos?| videos?)?|camgirl|webcam sex)\b",
    r"\b(?:escort service|escorts?|sexual services?|hookup sex|casual sex|live sex|sex chat|sticky service)\b",
    r"\b(?:blowjob|handjob|anal sex|oral sex|gangbang|cumshot|masturbat(?:e|ion|ing)|MILF|slut|pussy|cock|dick)\b",
    r"\b(?:married woman|woman gives|man(?:'s)? cock)\b.*\b(?:sticky service|cock|sex|porn)\b",
    r"\b(?:missav|onlyfans|pornhub|xvideos|xnxx|redtube|xhamster)\b",
]

def adult_content_reason(title: str = '', text: str = '', url: str = '') -> str:
    """High-confidence content gate for Hidden Leads / automatic contact promotion.

    Deliberately requires explicit adult-service/pornography language; isolated words such as
    'adult', 'dating', 'sex' in legitimate medical/social contexts do not trigger by themselves.
    """
    blob=' '.join((str(title or '')+' '+str(text or '')+' '+str(url or '')).split())[:30000]
    for pattern in _ADULT_CONTENT_PATTERNS:
        if re.search(pattern,blob,re.I):
            return 'explicit adult/sexual content'
    return ''


def soft_missing_reason(title: str = '', text: str = '') -> str:
    blob = ' '.join((str(title or '') + ' ' + str(text or '')).split())[:50000]
    if not blob:
        return ''
    for pattern, reason in _SOFT_MISSING_PATTERNS:
        if re.search(pattern, blob, re.I):
            return reason
    return ''




# Page-level unavailability signals are intentionally narrower than soft_missing_reason().
# Leads and Address Book records can point to perfectly valid company/about/contact pages
# that contain no role language, so only actual page disappearance is a soft-404 there.
_PAGE_UNAVAILABLE_PATTERNS = [
    (r'\bpage\s+not\s+found\b|\b404\s+(?:error|not\s+found)\b', 'page not found'),
    (r'\b(?:this|the|requested)\s+(?:page|content|resource|listing)\s+(?:is\s+)?(?:no\s+longer\s+)?(?:available|accessible)\b', 'page is no longer available'),
    (r'\b(?:this|the|requested)\s+(?:page|content|resource|listing)\s+(?:has\s+been\s+)?(?:removed|deleted)\b', 'page was removed'),
    (r'\bthe\s+page\s+you\s+(?:requested|are\s+looking\s+for)\s+(?:does\s+not\s+exist|cannot\s+be\s+found|could\s+not\s+be\s+found)\b', 'page does not exist'),
    (r'\bcontent\s+(?:is\s+)?unavailable\b|\bpage\s+(?:is\s+)?unavailable\b', 'page is unavailable'),
]


def page_unavailable_reason(title: str = '', text: str = '') -> str:
    blob = ' '.join((str(title or '') + ' ' + str(text or '')).split())[:50000]
    if not blob:
        return ''
    for pattern, reason in _PAGE_UNAVAILABLE_PATTERNS:
        if re.search(pattern, blob, re.I):
            return reason
    return ''


# Salary/emoji fragments found in scraped job-board titles belong in the salary field, not
# in the role label. Keep technical punctuation such as C++, C#, .NET and hyphens intact.
_TITLE_SALARY_SEGMENT_RE = re.compile(
    r'\s*[\(\[][^\)\]]*(?:[$£€¥₹]|\b(?:USD|SGD|AUD|CAD|GBP|EUR|JPY|INR|MYR|HKD|NZD|CHF)\b)[^\)\]]*\s*[\)\]]',
    re.I,
)
_TITLE_INLINE_SALARY_RE = re.compile(
    r'\s*(?:[-–—|·:]\s*)?(?:💰\s*)?(?:~\s*)?(?:[$£€¥₹]|\b(?:USD|SGD|AUD|CAD|GBP|EUR|JPY|INR|MYR|HKD|NZD|CHF)\b)\s*\d[\d,.]*(?:\s*[kKmM])?(?:\s*(?:[-–—]|to)\s*(?:[$£€¥₹]|(?:USD|SGD|AUD|CAD|GBP|EUR|JPY|INR|MYR|HKD|NZD|CHF))?\s*\d[\d,.]*(?:\s*[kKmM])?)?(?:\s*(?:/|per\s+)(?:yr|year|month|mo|hour|hr))?',
    re.I,
)
_DECORATIVE_SYMBOL_RE = re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]')



_TITLE_COMPANY_SUFFIX_RE = re.compile(r'(?i)\s+at\s+[^•|–—-]+(?:\s*[•|–—-].*)?$')
_TITLE_GENERIC_TRAILER_RE = re.compile(r'(?i)\s+(?:with|using|for|who|that|where|to)\s+.+$')
_TITLE_SENTENCE_PREFIX_PATTERNS = [
    re.compile(r'(?i)^\s*(?:we\s+(?:are\s+)?|our\s+team\s+is\s+)?(?:looking|searching)\s+for\s+(?:an?\s+)?(?P<role>(?:experienced\s+)?[A-Za-z][A-Za-z0-9+#./& -]{2,90}?)(?=\s+(?:to|who|with|for|that|using)\b|[.,;]|$)'),
    re.compile(r'(?i)^\s*(?P<company>[A-Z][A-Za-z0-9 .&-]{1,80})\s+(?:is\s+|are\s+)?(?:seeking|hiring|looking\s+for|recruiting)\s+(?:an?\s+)?(?P<role>[A-Za-z][A-Za-z0-9+#./& -]{2,90}?)(?=\s+(?:to|who|with|for|that|using)\b|[.,;]|$)'),
    re.compile(r'(?i)^\s*(?:seeking|hiring|wanted|required)\s+(?:an?\s+)?(?P<role>[A-Za-z][A-Za-z0-9+#./& -]{2,90}?)(?=\s+(?:to|who|with|for|that|using)\b|[.,;]|$)'),
]
_BROWSER_CHROME_RE = re.compile(r'(?i)^(?:discover\s*)?find\s+jobs\s*for\s+recruiters\s*log\s+in\s*sign\s+up\s*')

_ROLE_TITLE_STOPWORDS = {'a','an','the','of','and','or','for','with','to','in','on','at','by','from'}
_ROLE_TITLE_ACRONYMS = {'ai','ml','qa','ui','ux','api','sdk','ios','gpu','cpu','fpga','rtos','bios','sdk','sre','devops','cicd','ci/cd','ea','mt5'}

def _title_case_role(value: str) -> str:
    text=' '.join(str(value or '').split()).strip(' -–—|·:;/,.')
    text=_TITLE_GENERIC_TRAILER_RE.sub('',text).strip(' -–—|·:;/,.')
    if not text:
        return ''
    words=[]
    for idx,word in enumerate(text.split()):
        raw=word.strip()
        low=raw.casefold()
        if not raw:
            continue
        if low in _ROLE_TITLE_ACRONYMS:
            words.append(raw.upper() if low not in {'ios','devops','ci/cd'} else {'ios':'iOS','devops':'DevOps','ci/cd':'CI/CD'}[low])
        elif idx>0 and low in _ROLE_TITLE_STOPWORDS:
            words.append(low)
        elif raw.isupper() and len(raw)<=5:
            words.append(raw)
        else:
            # Preserve punctuation while title-casing alphabetic runs.
            words.append(re.sub(r'[A-Za-z]+', lambda m: m.group(0)[:1].upper()+m.group(0)[1:].lower(), raw))
    return ' '.join(words).strip()

def extract_compact_role_title(value: str) -> str:
    """Derive a compact role title from scraped JD/search-title sentences.

    Examples: ``Senior Security Researcher at Infrawatch • London`` becomes
    ``Senior Security Researcher``; ``Looking for experienced programmer to ...`` becomes
    ``Experienced Programmer``. Returns an empty string when no safe compact title is found.
    """
    text=' '.join(str(value or '').replace('\u00a0',' ').split()).strip(' -–—|·:;/,')
    if not text:
        return ''
    text=_BROWSER_CHROME_RE.sub('',text).strip()
    # Common Wellfound/AngelList/listing pattern.
    if re.search(r'(?i)\s+at\s+',text):
        left=re.split(r'(?i)\s+at\s+',text,1)[0].strip(' -–—|·:;/,')
        if 4 <= len(left) <= 110 and _ROLE_WORD_RE.search(left):
            return _title_case_role(left)
    for pattern in _TITLE_SENTENCE_PREFIX_PATTERNS:
        m=pattern.search(text)
        if not m:
            continue
        role=(m.groupdict().get('role') or '').strip(' -–—|·:;/,.')
        role=_TITLE_GENERIC_TRAILER_RE.sub('',role).strip(' -–—|·:;/,.')
        # Keep only the most title-like prefix if the sentence capture still overreached.
        if len(role)>80:
            role=' '.join(role.split()[:8])
        if role and _ROLE_WORD_RE.search(role):
            return _title_case_role(role)
    return ''

def normalize_opportunity_title(value: str):
    """Return (clean title, removed salary evidence) for a scraped role title."""
    original=sanitize_mixed_script_title(value)
    if not original:
        return '', ''
    salary_parts=[]
    def _capture(match):
        salary_parts.append(match.group(0).strip(' ()[]-|·:'))
        return ' '
    text=_TITLE_SALARY_SEGMENT_RE.sub(_capture, original)
    # Some boards prepend their helper/product UI instead of the role title, e.g.
    # "Cover Letter Assistant About this role. Senior Sales Engineer". Strip that
    # chrome before compact role extraction so persisted rows keep the actual vacancy.
    text=re.sub(r'(?is)^\s*(?:cover\s+letter\s+assistant|resume\s+assistant|cv\s+assistant)\b(?:\s+about\s+this\s+role\.?|\s+for\s+this\s+role\.?|[^A-Za-z0-9]{0,40})*\s*',' ',text)
    text=re.sub(r'(?is)^\s*about\s+this\s+role\.?\s*',' ',text)
    text=_TITLE_INLINE_SALARY_RE.sub(_capture, text)
    text=_DECORATIVE_SYMBOL_RE.sub(' ',text)
    text=re.sub(r'\s{2,}',' ',text).strip(' -–—|·:;/,')
    # Remove empty separators left before "at Company" after a salary segment.
    text=re.sub(r'\s+[-–—|·:]\s+(?=at\s+)', ' ', text, flags=re.I)
    compact=extract_compact_role_title(text)
    if compact:
        return compact, ' '.join(x for x in salary_parts if x)[:300]
    return (text or original), ' '.join(x for x in salary_parts if x)[:300]


def sanitize_mixed_script_title(value: str) -> str:
    """Strip stray non-Latin/search-shell fragments from role/company display text."""
    text = ' '.join(str(value or '').replace('\u00a0', ' ').split()).strip()
    if not text:
        return text
    # A title made entirely from CJK/Korean/etc. is usually an indexed/search shell label
    # in this English ScoutBox role field. Suppress it rather than presenting it as a role.
    if _FOREIGN_SCRIPT_RE.search(text) and not _LATIN_ROLE_RE.search(text):
        return ''
    if _FOREIGN_SCRIPT_RE.search(text):
        first=_FOREIGN_SCRIPT_RE.search(text)
        prefix=text[:first.start()].strip(' -–—|·:;/,') if first else ''
        # For fragments like "FuriosaAI 서울 2주 전 ..." the left side is the real
        # company/role label and everything after the first Korean/CJK run is browser chrome.
        if prefix and re.search(r'[A-Za-z]{2,}',prefix) and not _ROLE_WORD_RE.search(text[first.end():]):
            text=prefix
        else:
            text = _FOREIGN_SCRIPT_RE.sub(' ', text)
    text=re.sub(r'(?i)\b(?:new window|opens? in new|view who|applicants?|posted|promoted|save job|apply now|recruitment closed|job closed)\b.*$',' ',text)
    text=re.sub(r'(?i)\b(?:support|people|activity|less than|over|under)\s+\d+\b.*$',' ',text)
    # Clean separators left behind by e.g. "Engineer - 채용 | Company" without touching C/C++.
    text = re.sub(r'\s+(?:[-–—|·:/]\s*){2,}', ' - ', text)
    text = re.sub(r'\s*[-–—|·:/]\s*$', '', text)
    text = re.sub(r'^\s*[-–—|·:/]\s*', '', text)
    text = re.sub(r'\s{2,}', ' ', text).strip(' -–—|·:;/,')
    return text


def _parse_date_text(value: str):
    raw = ' '.join(str(value or '').split()).strip().strip('.,;')
    if not raw:
        return None
    # ISO first.
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except Exception:
        pass
    candidates = [
        '%b %d, %Y','%B %d, %Y','%d %b %Y','%d %B %Y','%Y-%m-%d','%Y/%m/%d',
        '%m/%d/%Y','%d/%m/%Y','%b. %d, %Y','%B %d %Y',
    ]
    for fmt in candidates:
        try:
            dt = datetime.strptime(raw, fmt)
            return timezone.make_aware(dt, timezone.get_current_timezone())
        except Exception:
            continue
    return None


def explicit_post_date_signal(text: str = '', *, schema_date: str = '', final_url: str = ''):
    """Extract high-confidence explicit posted/published dates before using an LLM."""
    if schema_date:
        dt = _parse_date_text(schema_date)
        if dt and dt <= timezone.now() + timedelta(days=1):
            return {'label':'JobPosting schema · datePosted','date':dt,'confidence':98,'source':'Page content',
                    'url':final_url,'note':f'datePosted={schema_date}'[:500],'meaning':'posted'}
    sample=' '.join(str(text or '')[:40000].split())
    # Do not include closing/deadline labels here; those are not posting dates.
    month=r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    date=r'(?:\d{4}-\d{1,2}-\d{1,2}|'+month+r'\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+'+month+r'\.?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})'
    patterns=[
        (r'\bposted\s+on\s+('+date+r')\b','posted'),
        (r'\bdate\s+posted\s*[:\-]?\s*('+date+r')\b','posted'),
        (r'\bpublished\s+on\s+('+date+r')\b','published'),
        (r'\bpublication\s+date\s*[:\-]?\s*('+date+r')\b','published'),
        (r'\bposted\s*[:\-]\s*('+date+r')\b','posted'),
    ]
    for pattern, meaning in patterns:
        m=re.search(pattern,sample,re.I)
        if not m:
            continue
        dt=_parse_date_text(m.group(1).replace('Sept','Sep'))
        if dt and dt <= timezone.now()+timedelta(days=1):
            phrase=m.group(0)[:180]
            return {'label':'Page content · '+('posted date' if meaning=='posted' else 'publication date'),
                    'date':dt,'confidence':96,'source':'Page content','url':final_url,'note':phrase,'meaning':meaning}
    return None



def _role_location_scope(text: str = '') -> str:
    """Return only the current job-posting section for role-location extraction."""
    raw = str(text or '').replace('\r', '\n')[:70000]
    if not raw:
        return ''
    # Drop related/recommended/footer/company panels.  These sections often contain other
    # roles with their own locations and must never influence the current opportunity.
    boundary = re.search(
        r'(?im)^\s*(?:related jobs|related remote jobs|recommended jobs|similar jobs|more opportunities|keep exploring|matched by job category|about the company|company overview|other jobs at|more jobs from|open roles|footer|privacy policy|terms of service)\b',
        raw,
    )
    if boundary:
        raw = raw[:boundary.start()]
    # Prefer the role body/header around the first known role-location marker when there is
    # lots of navigation before the post.  Keep a modest window after the marker so later
    # benefits/marketing copy does not become location evidence.
    marker = re.search(r'(?im)^\s*(?:remote from|job location|work location|role location|location requirements?|eligible locations?|office|workplace|location)\s*[:|\-]?\s*$', raw)
    if marker:
        return raw[max(0, marker.start()-2000): marker.start()+12000]
    return raw[:30000]


def extract_role_location(text: str = '', location_hint=''):
    """Return current-job location text from structured or role-scoped evidence only.

    The extractor deliberately ignores related-job cards, footer/company marketing copy,
    and generic words such as "worldwide" unless they are part of a concrete, current-role
    location field handled elsewhere.  LLM/body fallbacks must not override adapter/header
    evidence.
    """
    forbidden = {'remote','fully remote','not specified','unknown','worldwide','global','anywhere','remote worldwide','remote anywhere','work from anywhere'}
    def clean(value):
        value=' '.join(str(value or '').replace('\\n',' ').replace('\n',' ').replace('\xa0',' ').split()).strip(' |,;:-')
        value=re.split(r'(?i)\b(?:apply now|sign in|save|visa sponsorship|relocation|employment type|job type|about the job|about the role|salary|department|employment|experience|published|apply before|work type|compensation|related jobs|related remote jobs|recommended jobs|similar jobs|more opportunities|keep exploring|matched by job category|about the company)\b',value,1)[0].strip(' |,;:-')
        return value[:240]
    def from_obj(obj):
        if isinstance(obj,str): return clean(obj)
        if isinstance(obj,list):
            vals=[]
            for x in obj:
                item=from_obj(x)
                if item and item not in vals:
                    vals.append(item)
            if len(vals) > 3:
                return ''
            return ' / '.join(vals)[:240]
        if not isinstance(obj,dict): return ''
        if isinstance(obj.get('address'),dict):
            a=obj['address']; vals=[]
            for key in ('addressLocality','addressRegion','addressCountry'):
                v=a.get(key)
                if isinstance(v,dict): v=v.get('name') or v.get('value')
                v=clean(v)
                if v and v not in vals: vals.append(v)
            if vals: return ', '.join(vals)[:240]
        for key in ('name','addressLocality','addressRegion','addressCountry'):
            v=obj.get(key)
            if isinstance(v,dict): v=v.get('name') or v.get('value')
            v=clean(v)
            if v: return v
        return ''
    hint=location_hint
    if isinstance(hint,str) and hint.strip().startswith(('[','{')):
        try: hint=json.loads(hint)
        except Exception: pass
    structured=from_obj(hint)
    sample=_role_location_scope(text)
    patterns=(
        r'(?im)^\s*(?:remote from|job location|work location|role location|location requirements?|eligible locations?|workplace|office|location)\s*[:|\-]?\s*([^\n]{2,180})',
        r'(?im)^\s*(?:remote from|job location|work location|role location|location requirements?|eligible locations?|workplace|office|location)\s*[:|\-]?\s*$\s*([^\n]{2,180})',
        r'(?i)\b(?:this|the) role is (?:fully remote;?\s*)?(?:only\s+)?open to candidates based in\s+([^\n.;]{2,180})',
        r'(?i)\b(?:this|the) role is (?:available|open) in (?:the following locations?:\s*)?([^\n.;]{2,180})',
        r'(?i)\b(?:this|the) role is based in\s+([^\n.]{2,160})',
        r'(?i)\b(?:this|the) position is based in\s+([^\n.]{2,160})',
        r'(?i)\b(?:applicants?|candidates?)\s+(?:must|should|need to)\s+be\s+(?:located|based)\s+in\s+([^\n.;]{2,160})',
        r'(?i)\b(?:applicants?|candidates?)\s+(?:must|should|need to)\s+(?:live|reside)\s+in\s+([^\n.;]{2,160})',
        r'(?i)\b(?:remote|distributed)\s+(?:role|position|job)?\s*(?:from|in|within)\s+([^\n.;]{2,160})',
    )
    for pat in patterns:
        m=re.search(pat,sample)
        if not m: continue
        value=clean(m.group(1))
        if value and value.casefold() not in forbidden:
            return value
    if structured and structured.casefold() not in forbidden:
        return structured
    return ''


_REMOTE_WORK_PATTERNS=(
    r'\b(?:fully|100%|completely)\s+remote\b',
    r'\bremote[- ]first\b',
    r'\bremote\s+(?:role|position|job|opportunity|work)\b',
    r'\b(?:role|position|job|workplace(?: type)?|work location|location)\s*(?:is|:|-)?\s*remote\b',
    r'\bwork(?:ing)?\s+remotely\b',
    r'\bremote\s+work(?:ing)?\b',
    r'\bwork\s+from\s+home\b',
    r'\bhome[- ]based\b',
    r'\bwork\s+from\s+anywhere\b',
    r'\bremote\s+(?:in|from|within)\s+[a-z]'
)
_REMOTE_TECHNICAL_PATTERNS=(
    r'\bremote\s+(?:access|desktop|system|systems|server|servers|host|hosts|device|devices|control|monitoring|management|support|site|sites|terminal|telemetry|debug(?:ging)?|connection|connections|session|sessions|procedure call|rpc)\b',
    r'\b(?:ssh|rdp|vnc)\s+remote\b',
)


def work_arrangement_evidence(text: str = '', remote_text: str = '', title: str = '', *, structured_remote=False):
    """Ground a remote/hybrid/on-site classification in explicit role-level evidence.

    Semantic similarity is not evidence of a working arrangement. Phrases such as
    "growing your career", "flexible spending", remote access, remote systems and SEO
    collection titles must never create a Remote/Hybrid badge. A positive result therefore
    requires wording that directly describes where/how this role is worked, or trusted
    structured workplace metadata from a direct source adapter.
    """
    structured=' '.join(str(remote_text or '').split()).strip()
    structured_key=structured.casefold().strip(' .,:;-')
    if structured_remote:
        if structured_key in {'hybrid','hybrid remote','remote hybrid'} or re.fullmatch(r'hybrid(?:\s*[·|,-].*)?',structured_key):
            return {'confirmed':True,'status':'hybrid','label':'Hybrid','confidence':98,'reason':'Structured source explicitly marks the role as hybrid.','signal':structured[:120]}
        if structured_key in {'on-site','onsite','on site','office based','office-based'} or re.fullmatch(r'(?:on[- ]?site|office[- ]based)(?:\s*[·|,-].*)?',structured_key):
            return {'confirmed':True,'status':'onsite','label':'On-site','confidence':98,'reason':'Structured source explicitly marks the role as on-site.','signal':structured[:120]}
        if structured_key in {
            'remote','fully remote','100% remote','remote first','remote-first','worldwide',
            'anywhere','global remote','work from anywhere','work from home',
        }:
            status='fully_remote' if structured_key in {'fully remote','100% remote','worldwide','anywhere','global remote','work from anywhere'} else 'remote'
            return {'confirmed':True,'status':status,'label':('Fully remote' if status=='fully_remote' else 'Remote'),'confidence':97,'reason':'Structured source explicitly marks the role as remote.','signal':structured[:120]}

    raw_title=str(title or '')
    blob=' '.join((raw_title+' '+str(text or '')[:35000]).split()).casefold()
    collection_title=bool(re.search(r'\bjobs?\s+in\s+remote\b|\bremote\s+jobs?\s*(?:[-|–—]|$)',raw_title.casefold()))
    technical=[]
    for pat in _REMOTE_TECHNICAL_PATTERNS:
        m=re.search(pat,blob,re.I)
        if m: technical.append(m.group(0))

    hybrid_patterns=(
        r'\bhybrid\s+(?:role|position|job|work|working|workplace|arrangement|schedule|model)\b',
        r'\b(?:role|position|job|workplace(?: type)?|work arrangement|working model)\s*(?:is|:|-)\s*hybrid\b',
        r'\bhybrid[- ]working\b',
        r'\b(?:work|working)\s+(?:a\s+)?hybrid\s+(?:schedule|model|arrangement)\b',
        r'\b(?:one|two|three|four|five|[1-5])\s+days?\s+(?:a|per)\s+week\s+(?:in|at)\s+(?:the\s+)?office\b',
        r'\bsplit\s+(?:your\s+)?time\s+between\s+(?:home|remote)\s+and\s+(?:the\s+)?office\b',
    )
    onsite_patterns=(
        r'\b(?:on[- ]site|onsite)\s+(?:role|position|job|work|working|workplace|only)\b',
        r'\b(?:role|position|job|workplace(?: type)?|work arrangement|working model)\s*(?:is|:|-)\s*(?:on[- ]site|onsite)\b',
        r'\boffice[- ]based\s+(?:role|position|job|work)\b',
        r'\b(?:must|required to)\s+(?:work|be)\s+(?:on[- ]site|onsite|in (?:the )?office)\b',
        r'\bno\s+remote\s+(?:work|working|option)\b',
    )
    for pat in hybrid_patterns:
        m=re.search(pat,blob,re.I)
        if m:
            return {'confirmed':True,'status':'hybrid','label':'Hybrid','confidence':96,'reason':'Fetched role page explicitly describes a hybrid working arrangement.','signal':m.group(0)[:120]}
    for pat in onsite_patterns:
        m=re.search(pat,blob,re.I)
        if m:
            return {'confirmed':True,'status':'onsite','label':'On-site','confidence':96,'reason':'Fetched role page explicitly describes an on-site working arrangement.','signal':m.group(0)[:120]}

    positives=[]
    for pat in _REMOTE_WORK_PATTERNS:
        m=re.search(pat,blob,re.I)
        if m: positives.append(m.group(0))
    if positives and not collection_title:
        status='fully_remote' if re.search(r'\b(?:fully|100%|completely)\s+remote\b|\bwork\s+from\s+anywhere\b',positives[0],re.I) else 'remote'
        return {'confirmed':True,'status':status,'label':('Fully remote' if status=='fully_remote' else 'Remote'),'confidence':94,'reason':'Fetched role page explicitly describes remote work.','signal':positives[0][:120]}
    if technical:
        return {'confirmed':False,'status':'unknown','label':'Unknown','confidence':95,'reason':'The page uses remote in a technical/system context, not as a working arrangement.','signal':technical[0][:120]}
    return {'confirmed':False,'status':'unknown','label':'Unknown','confidence':90,'reason':'No explicit role-level remote/hybrid/on-site working-arrangement evidence was found on the fetched page.','signal':''}


def remote_work_evidence(text: str = '', remote_text: str = '', title: str = '', *, structured_remote=False):
    """Backward-compatible remote-only evidence helper."""
    row=work_arrangement_evidence(text,remote_text,title,structured_remote=structured_remote)
    if row.get('confirmed') and row.get('status') in {'fully_remote','remote'}:
        return row
    if row.get('confirmed'):
        return {'confirmed':False,'confidence':row.get('confidence',90),'reason':f"Page explicitly describes {row.get('label','a non-remote arrangement')}, not remote work.",'signal':row.get('signal','')}
    return row


def normalize_remote_constraints(text: str = '', remote_text: str = ''):
    """Return deterministic remote geography when the page explicitly limits eligibility."""
    sample=' '.join((str(remote_text or '')+' '+str(text or '')[:30000]).split())
    low=sample.casefold()
    worldwide=bool(re.search(r'\b(?:worldwide|anywhere in the world|work from anywhere|global remote)\b',low))
    explicit_remote=bool(remote_work_evidence(text,remote_text,structured_remote=True).get('confirmed'))
    # Strong structured phrases from boards such as Himalayas.
    windows=[]
    for pat in (
        r'location requirements?\s*[:\-]?\s*(.{0,180})',
        r'hiring timezones?\s*[:\-]?\s*(.{0,180})',
        r'(?:candidate|applicant|employee)s?\s+(?:must|should)\s+be\s+(?:based|located)\s+(?:in|within)\s+(.{0,160})',
        r'remote(?: work)?\s+(?:in|from|within)\s+(.{0,160})',
        r'\bremote\s*[:\-·]\s*(.{0,120})',
    ):
        m=re.search(pat,sample,re.I)
        if m:
            windows.append(m.group(1))
    # Only a structured/explicit eligibility window is allowed to create a country
    # restriction. A company HQ/country mentioned elsewhere on a remote page is not enough.
    hay=' '.join(windows)
    countries=[]
    alias_patterns={'United States':r'\b(?:US|USA|U\.S\.|United States(?: of America)?)\b',
                    'United Kingdom':r'\b(?:UK|U\.K\.|United Kingdom|Great Britain|Britain)\b'}
    for country in _COUNTRY_NAMES:
        pat=alias_patterns.get(country,r'\b'+re.escape(country)+r'\b')
        if re.search(pat,hay,re.I) and country not in countries:
            countries.append(country)
    # Explicit location/timezone requirement blocks outrank generic badges such as
    # "remote worldwide" that can appear elsewhere in a board shell or SEO chrome.
    constrained=bool(countries and windows)
    if constrained:
        chosen=countries[0]
        return {'status':'remote','label':f'Remote · {chosen}','country':chosen,'countries':countries[:8],
                'confidence':96,'reason':'Page explicitly limits remote location/timezone eligibility.'}
    if worldwide and explicit_remote:
        return {'status':'fully_remote','label':'Fully remote','country':'','countries':[],
                'confidence':94,'reason':'Page explicitly allows worldwide/anywhere remote work.'}
    return None
