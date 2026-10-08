from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from django.utils import timezone

_CURRENCY_ALIASES={
    'S$':'SGD','SGD':'SGD','US$':'USD','USD':'USD','$':'USD','A$':'AUD','AUD':'AUD',
    'C$':'CAD','CAD':'CAD','£':'GBP','GBP':'GBP','€':'EUR','EUR':'EUR','JPY':'JPY','¥':'JPY',
    'INR':'INR','₹':'INR','MYR':'MYR','RM':'MYR','HKD':'HKD','NZD':'NZD','CHF':'CHF',
}
_PERIOD_ALIASES={
    'year':'year','yr':'year','yearly':'year','annual':'year','annually':'year','pa':'year','p.a.':'year',
    'month':'month','mo':'month','monthly':'month','day':'day','daily':'day','hour':'hour','hr':'hour','hourly':'hour',
    'project':'project','contract':'project',
}
_PERIOD_FACTOR={'year':Decimal('1'),'month':Decimal('12'),'day':Decimal('260'),'hour':Decimal('2080')}


_SALARY_NOISE_PATTERNS=(
    r'\bsign\s+in\b.{0,120}\b(?:salary|pay)\b',
    r'\badd\s+(?:your\s+)?salary\b',
    r'\bsee\s+(?:salary|pay)\s+matches\b',
    r'\bcompetitive\s+(?:salary|compensation|pay)\b',
    r'\bperformance[- ]based\s+bonus\b',
)

def salary_text_has_numeric_amount(value):
    """True only for compensation text containing an actual numeric amount.

    Job-board boilerplate such as ``Competitive salary`` or ``Sign in and add your
    salary`` is not compensation data and must never occupy list-view space.
    """
    text=' '.join(str(value or '').split()).strip()
    if not text or not re.search(r'\d',text):
        return False
    low=text.casefold()
    # Reject year-only snippets such as "Backend Developer Salary in Germany [2023]".
    # A four-digit publication/report year is metadata, not compensation.
    numeric_tokens=[int(x) for x in re.findall(r'(?<!\d)(\d{4})(?!\d)', text)]
    all_number_tokens=re.findall(r'(?<![A-Za-z0-9])\d[\d,.]*\s*[kKmM]?(?![A-Za-z0-9])', text)
    has_currency=bool(re.search(r'[$£€¥₹]|\b(?:SGD|USD|AUD|CAD|GBP|EUR|JPY|INR|MYR|HKD|NZD|CHF)\b', text, re.I))
    has_pay_period=bool(re.search(r'\b(?:per|/\s*)(?:year|yr|month|mo|day|hour|hr)\b|\b(?:annual|annually|monthly|daily|hourly)\b', text, re.I))
    if all_number_tokens and numeric_tokens and len(all_number_tokens)==len(numeric_tokens) and all(1900 <= y <= 2100 for y in numeric_tokens) and not has_currency and not has_pay_period:
        return False
    currency_amount=bool(re.search(r'(?:[$£€¥₹]|\b(?:SGD|USD|AUD|CAD|GBP|EUR|JPY|INR|MYR|HKD|NZD|CHF)\b)\s*\d|\d[\d,.]*\s*[kKmM]?\+?\s*(?:[$£€¥₹]|\b(?:SGD|USD|AUD|CAD|GBP|EUR|JPY|INR|MYR|HKD|NZD|CHF)\b)',text,re.I))
    salary_number=bool(re.search(r'\b(?:salary|compensation|pay\s+range|base\s+pay|base\s+salary|remuneration|rate)\b.{0,90}\d|\d.{0,90}\b(?:per\s+(?:year|month|day|hour)|/\s*(?:yr|year|mo|month|hr|hour))\b',text,re.I|re.S))
    if not (currency_amount or salary_number):
        return False
    # Boilerplate is rejected when it is the only apparent salary evidence. A real
    # numeric range on the same line still wins over adjacent job-board marketing copy.
    if any(re.search(p,low,re.I|re.S) for p in _SALARY_NOISE_PATTERNS) and not currency_amount:
        return False
    return True

def salary_urls_equivalent(a,b):
    """Compare salary/source URLs without fragments/trailing slash noise."""
    from urllib.parse import urlsplit,urlunsplit
    def norm(v):
        try:
            u=urlsplit(str(v or '').strip())
            if u.scheme not in ('http','https') or not u.netloc: return ''
            path=(u.path or '/').rstrip('/') or '/'
            return urlunsplit((u.scheme.lower(),u.netloc.lower(),path,u.query,''))
        except Exception:
            return ''
    na,nb=norm(a),norm(b)
    return bool(na and nb and na==nb)


def _compact(value, limit=300):
    text=' '.join(str(value or '').replace('\xa0',' ').split()).strip()
    if len(text)<=limit: return text
    return text[:limit].rsplit(' ',1)[0].rstrip(' ,;:-')+'…'


def _number(value):
    text=str(value or '').replace(',','').strip().lower().rstrip('+')
    mult=Decimal('1')
    if text.endswith('k'):
        mult=Decimal('1000'); text=text[:-1]
    elif text.endswith('m'):
        mult=Decimal('1000000'); text=text[:-1]
    try:
        return Decimal(text)*mult
    except (InvalidOperation,ValueError):
        return None


def _currency(token):
    token=str(token or '').strip()
    return _CURRENCY_ALIASES.get(token,_CURRENCY_ALIASES.get(token.upper(),''))


def _period(token):
    token=str(token or '').strip().casefold().rstrip('.')
    return _PERIOD_ALIASES.get(token,'')


def parse_salary_text(value):
    """Conservatively parse a compensation string without network/AI calls.

    A parse is accepted only when a currency and a pay period are present, or the
    surrounding text clearly says salary/compensation/pay. This avoids treating random
    prices/revenue figures in a captured page as job compensation.
    """
    text=_compact(value,900)
    if not text:
        return {}
    # Qualitative/job-board boilerplate is not salary data. Require a numeric amount
    # before parsing so phrases such as "Competitive salary" never survive.
    if not salary_text_has_numeric_amount(text):
        return {}
    lowered=text.casefold()
    salary_context=bool(re.search(r'\b(?:salary|compensation|pay range|base pay|base salary|remuneration|rate)\b',lowered))
    cur=r'(S\$|SGD|US\$|USD|A\$|AUD|C\$|CAD|GBP|£|EUR|€|JPY|¥|INR|₹|MYR|RM|HKD|NZD|CHF|\$)'
    num=r'(\d{1,3}(?:[,.]\d{3})*(?:\.\d+)?\s*[kKmM]?\+?|\d+(?:\.\d+)?\s*[kKmM]?\+?)'
    per=r'(?:per\s+|/\s*|a\s+)?(year|yr|yearly|annual|annually|month|mo|monthly|day|daily|hour|hr|hourly|project)\b'
    patterns=[
        rf'{cur}\s*{num}\s*(?:[-–—]|to)\s*(?:{cur}\s*)?{num}\s*(?:{per})?',
        rf'{num}\s*(?:[-–—]|to)\s*{num}\s*{cur}\s*(?:{per})?',
        rf'{cur}\s*{num}\s*(?:{per})',
    ]
    for pat in patterns:
        m=re.search(pat,text,re.I)
        if not m: continue
        groups=list(m.groups())
        # Extract currency tokens, number tokens and period token by value rather than
        # positional assumptions because the regex alternatives contain optional groups.
        curr=''; nums=[]; period=''
        for g in groups:
            if g is None: continue
            gc=str(g).strip()
            if not curr and _currency(gc): curr=_currency(gc); continue
            if not period and _period(gc): period=_period(gc); continue
            n=_number(gc)
            if n is not None: nums.append(n)
        if not curr or not nums:
            continue
        if not period and not salary_context:
            continue
        matched=_compact(m.group(0),180)
        if not period:
            # Salary context with no period is still useful as text, but numeric preference
            # comparison would be misleading. Keep only the matched compensation fragment
            # rather than echoing a whole flattened job-description line into the list view.
            return {'currency':curr,'min':nums[0],'max':nums[1] if len(nums)>1 else nums[0],'period':'','text':matched}
        lo=nums[0]; hi=nums[1] if len(nums)>1 else nums[0]
        if hi<lo: lo,hi=hi,lo
        return {'currency':curr,'min':lo,'max':hi,'period':period,'text':matched}
    # Some source pages omit a currency but still give an explicit numeric salary/pay
    # range. Preserve that useful information for display, but leave currency blank so
    # expectation comparison cannot accidentally assume USD/SGD.
    if salary_context:
        plain_num=r'(\d{1,3}(?:[,.]\d{3})*(?:\.\d+)?\s*[kKmM]?\+?|\d+(?:\.\d+)?\s*[kKmM]?\+?)'
        pm=re.search(rf'{plain_num}\s*(?:[-–—]|to)\s*{plain_num}\s*(?:{per})?',text,re.I)
        if pm:
            vals=[]; period=''
            for g in pm.groups():
                if g is None: continue
                if not period and _period(g): period=_period(g); continue
                n=_number(g)
                if n is not None: vals.append(n)
            if len(vals)>=2:
                lo,hi=vals[0],vals[1]
                if hi<lo: lo,hi=hi,lo
                return {'currency':'','min':lo,'max':hi,'period':period,'text':_compact(pm.group(0),180)}
    return {}


def _salary_windows(text):
    """Yield compact compensation-looking fragments from retained job text.

    Keep this deterministic and cheap: Local Discovery calls it inline, so this helper
    must never perform network or AI work. Prefer line/sentence-sized fragments so a
    valid salary estimate is not drowned out by unrelated currency figures elsewhere
    on a large captured page.
    """
    raw=str(text or '').replace('\r\n','\n').replace('\r','\n')
    if not raw:
        return
    key=re.compile(r'(?i)(?:salary(?:\s+estimate|\s+range)?|estimated\s+salary|compensation|base\s+pay|base\s+salary|pay\s+range|remuneration|\bSGD\b|\bUSD\b|S\$|US\$)')
    seen=set()
    # Lines are the cleanest source for strings such as "Salary estimate: $98,000 - $120,000+ ...".
    for line in raw.split('\n'):
        line=' '.join(line.split()).strip()
        if not line or not key.search(line):
            continue
        frag=_compact(line,520)
        norm=frag.casefold()
        if norm not in seen:
            seen.add(norm); yield frag
    # Some HTML/text extraction flattens the entire page onto one line; retain short windows.
    for hit in list(key.finditer(raw))[:12]:
        start=max(0,hit.start()-100); end=min(len(raw),hit.start()+460)
        frag=_compact(raw[start:end],520)
        norm=frag.casefold()
        if frag and norm not in seen:
            seen.add(norm); yield frag


def _retained_sources(opportunity):
    facts=opportunity.extracted_facts if isinstance(getattr(opportunity,'extracted_facts',{}),dict) else {}
    cloud=facts.get('cloud_research') if isinstance(facts.get('cloud_research'),dict) else {}
    role=facts.get('role_info') if isinstance(facts.get('role_info'),dict) else {}
    ai=facts.get('ai_job_summary') if isinstance(facts.get('ai_job_summary'),dict) else {}
    target=str(getattr(opportunity,'target_url','') or getattr(opportunity,'url','') or '')

    # Retained source/JD evidence outranks AI/web estimates. This is deliberately first:
    # ScoutBox may already hold a useful source-page benchmark even if a later cloud
    # salary lookup was noisy or mismatched to another region/level.
    for value in (getattr(opportunity,'description',''),ai.get('source_text'),role.get('summary'),getattr(opportunity,'raw_search_snippet','')):
        for frag in _salary_windows(value):
            lower=frag.casefold()
            estimate=bool(re.search(r'\b(?:salary\s+estimate|estimated\s+salary|benchmark|market\s+(?:rate|range|estimate))\b',lower))
            source_type='job_estimate' if estimate else 'post'
            confidence=70 if estimate else 90
            yield frag,source_type,confidence,target

    # Cloud structured values remain useful fallbacks, but they must never replace a
    # salary/benchmark that is already present in the retained job description.
    if str(cloud.get('salary') or '').strip():
        yield str(cloud.get('salary')), 'post', 84, target
    if str(cloud.get('salary_estimate') or '').strip():
        yield str(cloud.get('salary_estimate')), 'external', 62, target

    summary=str(role.get('summary') or '')
    for label,stype,confidence in (('Advertised salary:','post',84),('Salary estimate:','job_estimate',68)):
        m=re.search(re.escape(label)+r'\s*(.+?)(?:\n|$)',summary,re.I)
        if m: yield m.group(1),stype,confidence,target

def salary_from_retained_opportunity(opportunity):
    for raw,source_type,confidence,url in _retained_sources(opportunity):
        parsed=parse_salary_text(raw)
        if not parsed:
            continue
        text=_compact(parsed.get('text') or raw,300)
        if not text or not salary_text_has_numeric_amount(text): continue
        return {
            'salary_text':text,
            'salary_currency':parsed.get('currency',''),
            'salary_min':parsed.get('min'),
            'salary_max':parsed.get('max'),
            'salary_period':parsed.get('period',''),
            'salary_source_type':source_type,
            'salary_source_url':url[:1000],
            'salary_confidence':confidence,
            'salary_checked_at':timezone.now(),
        }
    return {}


def salary_from_cloud_result(result, source_url=''):
    row=result if isinstance(result,dict) else {}
    advertised=str(row.get('salary') or row.get('advertised_salary') or '').strip()
    estimate=str(row.get('salary_estimate') or row.get('credible_salary_range') or '').strip()
    raw=advertised or estimate
    if not raw or not salary_text_has_numeric_amount(raw):
        return {}
    parsed=parse_salary_text(raw)
    if not parsed:
        return {}
    source_type='post' if advertised else 'external'
    confidence=92 if advertised else 65
    return {
        'salary_text':_compact(raw,300),
        'salary_currency':parsed.get('currency',''),
        'salary_min':parsed.get('min'),
        'salary_max':parsed.get('max'),
        'salary_period':parsed.get('period',''),
        'salary_source_type':source_type,
        'salary_source_url':str(source_url or row.get('exact_url') or row.get('url') or '')[:1000],
        'salary_confidence':confidence,
        'salary_checked_at':timezone.now(),
    }


def apply_salary_info(opportunity, info, *, save=True):
    if not info:
        return False
    fields=[]
    for field in ('salary_text','salary_currency','salary_min','salary_max','salary_period','salary_source_type','salary_source_url','salary_confidence','salary_checked_at'):
        if field in info:
            setattr(opportunity,field,info.get(field)); fields.append(field)
    if save and fields:
        opportunity.save(update_fields=list(dict.fromkeys(fields+['updated_at'])))
    return bool(fields)


def normalized_pay_preferences(profile_or_scope):
    """Return one normalized pay-preference list, including legacy preference fields.

    Older ScoutBox profiles can still carry only ``min_pay``/``pay_currency``/``pay_period``.
    The Engagement Preferences screen already displayed those values as a row, so every
    ranking/comparison path must see the same effective preferences rather than treating the
    visible row as missing configuration.
    """
    if isinstance(profile_or_scope, dict):
        scope=profile_or_scope
    else:
        scope=getattr(profile_or_scope,'scope_json',{})
        if not isinstance(scope,dict): scope={}
    raw=scope.get('pay_preferences')
    rows=raw if isinstance(raw,list) else []
    normalized=[]
    for pref in rows:
        if not isinstance(pref,dict) or pref.get('amount') in (None,''):
            continue
        normalized.append({
            'amount':pref.get('amount'),
            'currency':str(pref.get('currency') or '').strip().upper(),
            'period':str(pref.get('period') or '').strip().casefold(),
        })
    if not normalized and scope.get('min_pay') not in (None,''):
        normalized=[{
            'amount':scope.get('min_pay'),
            'currency':str(scope.get('pay_currency') or 'SGD').strip().upper(),
            'period':str(scope.get('pay_period') or 'year').strip().casefold(),
        }]
    return normalized


def salary_preference_match(opportunity, profile):
    """Compare compensation with Engagement Preferences when units are comparable.

    No FX conversion is invented. Different currencies return unknown rather than a false
    green/red judgment. Standard annualisation is used only for year/month/day/hour rates.
    """
    try:
        lo=Decimal(str(opportunity.salary_min)) if opportunity.salary_min is not None else None
        hi=Decimal(str(opportunity.salary_max)) if opportunity.salary_max is not None else lo
    except Exception:
        lo=hi=None
    currency=str(opportunity.salary_currency or '').upper(); period=str(opportunity.salary_period or '').casefold()
    if lo is None or not currency or period not in _PERIOD_FACTOR:
        return {'state':'unknown','label':'Expectation comparison unavailable'}
    prefs=normalized_pay_preferences(profile)
    compatible=[]
    for pref in prefs:
        if not isinstance(pref,dict) or str(pref.get('currency') or '').upper()!=currency: continue
        pp=str(pref.get('period') or '').casefold()
        if pp not in _PERIOD_FACTOR: continue
        try: amount=Decimal(str(pref.get('amount')))
        except Exception: continue
        compatible.append(amount*_PERIOD_FACTOR[pp])
    if not compatible:
        if prefs:
            return {'state':'unknown','label':f'No configured {currency} pay preference'}
        return {'state':'unknown','label':'No compensation preference configured'}
    threshold=max(compatible)
    annual_lo=lo*_PERIOD_FACTOR[period]; annual_hi=(hi or lo)*_PERIOD_FACTOR[period]
    if annual_lo>=threshold:
        return {'state':'meets','label':'Meets configured compensation expectation'}
    if annual_hi<threshold:
        return {'state':'below','label':'Below configured compensation expectation'}
    return {'state':'mixed','label':'Range overlaps configured compensation expectation'}


def source_label(opportunity):
    kind=str(getattr(opportunity,'salary_source_type','') or '').casefold()
    if kind=='post': return 'Job post'
    if kind=='job_estimate': return 'Job-description estimate'
    if kind=='external': return 'External research'
    if kind=='market': return 'Market estimate'
    return 'Source unknown'


def confidence_label(value):
    try: n=int(value or 0)
    except Exception: n=0
    if n>=80: return 'High'
    if n>=50: return 'Medium'
    if n>0: return 'Low'
    return 'Unknown'


def research_salary_cloud(opportunity):
    """Research missing compensation using the configured Cloud Web route only.

    This function is never called from Local AI Discovery. It is suitable for a deferred
    idle-time backfill and therefore cannot contend with the local GPU campaign path.
    """
    from .ai import cloud_discovery_route, web_search_with
    route=cloud_discovery_route('primary',stage='company_enrichment')
    if not route or not route.get('provider') or not route.get('model'):
        return {}
    prompt=(
        'Research compensation for this exact job using current public web sources. Prefer compensation explicitly stated in the exact job post. '
        'If it is not advertised, use only credible company-and-role/location-specific evidence; otherwise say not found. Do not invent a range. '
        'Return JSON only with keys found, salary, source_type (post/external/market), confidence (0-100), source_url. '
        'salary should be a short human-readable range including currency and period when known.\n\n'
        f'Company: {opportunity.company}\nRole: {opportunity.title}\nRole URL: {opportunity.target_url or opportunity.url}\n'
    )
    raw,meta=web_search_with(route.get('provider'),route.get('model'),prompt,stage='company_enrichment',timeout=120,budget_operation='salary_backfill')
    text=str(raw or '').strip()
    try:
        if '```' in text:
            m=re.search(r'```(?:json)?\s*(.*?)```',text,re.S|re.I)
            if m: text=m.group(1).strip()
        a=text.find('{'); b=text.rfind('}')
        data=json.loads(text[a:b+1]) if a>=0 and b>a else {}
    except Exception:
        data={}
    if not data.get('found') or not salary_text_has_numeric_amount(data.get('salary')):
        return {'salary_checked_at':timezone.now(),'salary_confidence':0,'salary_source_type':'unknown'}
    parsed=parse_salary_text(data.get('salary'))
    if not parsed:
        return {'salary_checked_at':timezone.now(),'salary_confidence':0,'salary_source_type':'unknown'}
    try: conf=max(1,min(100,int(data.get('confidence') or 60)))
    except Exception: conf=60
    stype=str(data.get('source_type') or 'external').casefold()
    if stype not in {'post','external','market'}: stype='external'
    return {
        'salary_text':_compact(data.get('salary'),300),'salary_currency':parsed.get('currency',''),
        'salary_min':parsed.get('min'),'salary_max':parsed.get('max'),'salary_period':parsed.get('period',''),
        'salary_source_type':stype,'salary_source_url':str(data.get('source_url') or opportunity.target_url or opportunity.url)[:1000],
        'salary_confidence':conf,'salary_checked_at':timezone.now(),
    }
