"""Cross-list and same-list data-quality helpers for ScoutBox 0.8.76.

The rules here are deliberately conservative: a concrete Opportunity wins over a
company-only Hidden Lead, duplicate rows are matched by normalized URL/domain plus
company/title evidence, and automatic Address Book collection keeps the most useful
recent contact for a company instead of accumulating generic mailboxes.
"""
from __future__ import annotations

import re
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from django.db.models import Q
from django.utils import timezone

from portal.models import Application, CompanyLead, Contact, Opportunity

_TRACKING_PREFIXES = ('utm_', 'ref', 'trk', 'tracking', 'source')
_TRACKING_KEYS = {'fbclid','gclid','mc_cid','mc_eid','campaign','campaign_id','lever-source','lever_origin'}
_SENIORITY_TOKENS = {'junior','jr','senior','sr','lead','principal','staff','associate','mid','midlevel','entry','graduate','intern','internship','i','ii','iii','iv'}
_ROLE_GENERIC_TOKENS = {'engineer','engineering','developer','development','manager','specialist','architect','software','role','position'}
_GENERIC_LOCALS = {
    'jobs','job','careers','career','recruiting','recruitment','talent','hiring',
    'info','hello','contact','office','team','support','service','admin','hr','people',
}


def normalized_url(value: str) -> str:
    """Canonical comparison URL; treats underscore/hyphen path variants as equivalent."""
    raw = str(value or '').strip()
    if not raw:
        return ''
    try:
        p = urlsplit(raw)
        host = (p.hostname or '').lower().removeprefix('www.')
        if not host:
            return ''
        port = f':{p.port}' if p.port and p.port not in (80, 443) else ''
        path = re.sub(r'[-_]+', '-', p.path or '/').rstrip('/') or '/'
        path = re.sub(r'/+', '/', path).lower()
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith(_TRACKING_PREFIXES)]
        return urlunsplit(('https', host + port, path, urlencode(q), ''))
    except Exception:
        return re.sub(r'[-_]+', '-', raw.lower().rstrip('/'))


def domain_key(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    if '@' in raw and '://' not in raw:
        raw = 'https://' + raw.split('@', 1)[1]
    if '://' not in raw:
        raw = 'https://' + raw
    try:
        host = (urlsplit(raw).hostname or '').lower().removeprefix('www.')
    except Exception:
        return ''
    if not host:
        return ''
    parts = [x for x in host.split('.') if x]
    # Good-enough registrable-domain comparison without introducing a PSL dependency.
    if len(parts) >= 3 and parts[-2:] in (['co','uk'], ['com','au'], ['co','jp'], ['com','sg']):
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:]) if len(parts) >= 2 else host


def company_key(name: str, url: str = '') -> str:
    text = ' '.join(str(name or '').split()).casefold()
    text = re.sub(r'\b(?:incorporated|inc|llc|ltd|limited|gmbh|ag|plc|corp|corporation|company|co)\b\.?', ' ', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text).strip()
    if text:
        return text
    return domain_key(url)


def title_key(title: str) -> str:
    text = re.sub(r'[^a-z0-9+#]+', ' ', str(title or '').casefold())
    return re.sub(r'\s+', ' ', text).strip()


def opportunity_identity(title: str, company: str, url: str = '') -> tuple[str, str, str]:
    return (normalized_url(url), company_key(company, url), title_key(title))



def vacancy_url_key(value: str) -> str:
    """Stable vacancy URL identity with tracking noise removed.

    This is deliberately more conservative than a redirect resolver: it never guesses
    that two different employer paths are the same vacancy, but it does make URLs from
    different discovery providers compare consistently once they resolve to the same
    employer/ATS destination.
    """
    raw = str(value or '').strip()
    if not raw:
        return ''
    try:
        p = urlsplit(raw)
        host = (p.hostname or '').lower().removeprefix('www.')
        if not host:
            return normalized_url(raw)
        port = f':{p.port}' if p.port and p.port not in (80, 443) else ''
        path = re.sub(r'/+', '/', p.path or '/').rstrip('/') or '/'
        query=[]
        for key, val in parse_qsl(p.query, keep_blank_values=True):
            low=key.casefold()
            if low in _TRACKING_KEYS or low.startswith(_TRACKING_PREFIXES):
                continue
            query.append((key,val))
        query.sort(key=lambda item:(item[0].casefold(), item[1]))
        return urlunsplit(('https', host + port, path.lower(), urlencode(query), ''))
    except Exception:
        return normalized_url(raw)


def requisition_keys(url: str = '', text: str = '') -> set[str]:
    """Extract only explicit job/requisition identifiers; avoid inventing IDs from slugs."""
    out=set()
    raw=str(url or '')
    try:
        p=urlsplit(raw)
        for key,val in parse_qsl(p.query, keep_blank_values=True):
            if key.casefold() in {'jid','jobid','job_id','job','req','reqid','req_id','requisition','requisition_id','gh_jid'}:
                cleaned=re.sub(r'[^a-z0-9_-]+','',str(val or '').casefold())
                if 3 <= len(cleaned) <= 80:
                    out.add(cleaned)
    except Exception:
        pass
    hay=' '.join(str(text or '').split())[:12000]
    for match in re.finditer(r'(?i)\b(?:requisition|req(?:uisition)?|job)\s*(?:id|#|number|no\.?)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]{2,40})\b', hay):
        value=re.sub(r'[^a-z0-9_-]+','',match.group(1).casefold())
        if value and not value.isalpha():
            out.add(value)
    return out


def _role_tokens(title: str) -> list[str]:
    tokens=re.findall(r'[a-z0-9+#.]+',str(title or '').casefold())
    return [t for t in tokens if t not in _SENIORITY_TOKENS]


def role_family_similarity(left: str, right: str) -> float:
    """Similarity for same-employer role-family checks without seniority noise."""
    a=_role_tokens(left); b=_role_tokens(right)
    if not a or not b:
        return 0.0
    sa=set(a); sb=set(b)
    da={t for t in sa if t not in _ROLE_GENERIC_TOKENS}
    db={t for t in sb if t not in _ROLE_GENERIC_TOKENS}
    if da and db:
        containment=len(da & db)/max(1,min(len(da),len(db)))
        jaccard=len(da & db)/max(1,len(da | db))
    else:
        containment=len(sa & sb)/max(1,min(len(sa),len(sb)))
        jaccard=len(sa & sb)/max(1,len(sa | sb))
    seq=__import__('difflib').SequenceMatcher(None,' '.join(a),' '.join(b)).ratio()
    return max(jaccard, (containment*0.75)+(seq*0.25))


def content_similarity(left: str, right: str) -> float:
    """Cheap bounded token similarity for role-responsibility differentiation."""
    def sig(value):
        words=re.findall(r'[a-z0-9+#.]{3,}',str(value or '').casefold()[:9000])
        stop={'the','and','with','for','you','your','our','this','that','from','will','are','job','role','team','work','working','experience','years','skills','using','about','have','has'}
        return {w for w in words if w not in stop}
    a=sig(left); b=sig(right)
    if not a or not b:
        return 0.0
    return len(a & b)/max(1,len(a | b))


def _location_key(value: str) -> str:
    text=re.sub(r'[^a-z0-9]+',' ',str(value or '').casefold()).strip()
    return re.sub(r'\b(?:remote|hybrid|onsite|on site|work from home)\b',' ',text).strip()


def materially_different_location(left: str, right: str) -> bool:
    a=_location_key(left); b=_location_key(right)
    if not a or not b:
        return False
    if a==b or a in b or b in a:
        return False
    sa=set(a.split()); sb=set(b.split())
    return bool(sa and sb and len(sa & sb)/max(1,min(len(sa),len(sb))) < 0.5)


def active_role_family_duplicate(title: str, company: str, url: str, description: str = '', *, role_location: str = '', country: str = '', exclude_id=None, days=180):
    """Find the same vacancy across providers without collapsing genuinely distinct roles.

    Different explicit requisition IDs or clearly different locations are treated as
    evidence that two same-family titles are separate vacancies. Otherwise, same-company
    title-family + responsibility similarity can merge Jobicy/ATS/employer rediscoveries.
    """
    since=timezone.now()-timedelta(days=max(30,int(days or 180)))
    qs=Opportunity.objects.filter(user_deleted=False,first_seen_by_portal__gte=since)
    if exclude_id:
        qs=qs.exclude(pk=exclude_id)
    incoming_company=company_key(company,url)
    narrowed=qs.filter(company__iexact=str(company or '').strip()) if str(company or '').strip() else qs.none()
    candidates=list(narrowed.only('id','title','company','url','target_url','canonical_url','search_url','description','raw_search_snippet','role_location','country','fit_score','last_seen')[:1500])
    if not candidates:
        candidates=list(qs.only('id','title','company','url','target_url','canonical_url','search_url','description','raw_search_snippet','role_location','country','fit_score','last_seen')[:2500])
    incoming_req=requisition_keys(url,description)
    incoming_loc=' '.join(x for x in (role_location,country) if str(x or '').strip())
    incoming_url=vacancy_url_key(url)
    best=None; best_score=0.0
    for row in candidates:
        row_url=row.target_url or row.canonical_url or row.url or row.search_url
        if incoming_url and vacancy_url_key(row_url)==incoming_url:
            return row
        if not incoming_company or company_key(row.company,row_url)!=incoming_company:
            continue
        family=role_family_similarity(title,row.title)
        if family < 0.72:
            continue
        old_text=row.description or row.raw_search_snippet or ''
        old_req=requisition_keys(row_url,old_text)
        if incoming_req and old_req and incoming_req.isdisjoint(old_req):
            continue
        row_loc=' '.join(x for x in (row.role_location,row.country) if str(x or '').strip())
        if materially_different_location(incoming_loc,row_loc) and not (incoming_req and old_req and not incoming_req.isdisjoint(old_req)):
            continue
        body=content_similarity(description,old_text)
        title_seq=__import__('difflib').SequenceMatcher(None,title_key(title),title_key(row.title)).ratio()
        score=max(family,body,title_seq)
        same_req=bool(incoming_req and old_req and not incoming_req.isdisjoint(old_req))
        if same_req or (description and old_text and family>=0.72 and body>=0.46) or (not description or not old_text) and title_seq>=0.96 and family>=0.90:
            if score>best_score:
                best=row; best_score=score
    return best


def company_concentration_decision(company: str, url: str, title: str, description: str, fit_score: int, *, role_location: str = '', country: str = '', days=14, base_fit_threshold=0):
    """Rolling employer-concentration guard for the primary Opportunity list.

    It is intentionally graded, not a permanent employer quota. A prolific employer can
    still contribute materially different high-fit roles, while repeated/similar roles are
    folded into an existing company row once concentration becomes excessive.
    """
    ck=company_key(company,url)
    if not ck:
        return {'allow':True,'count':0,'reason':'company identity unavailable','anchor':None,'materially_distinct':True,'stronger_fit':False}
    since=timezone.now()-timedelta(days=max(2,int(days or 14)))
    base=Opportunity.objects.filter(user_deleted=False,suppressed=False,first_seen_by_portal__gte=since).exclude(status='rejected')
    exact=list(base.filter(company__iexact=str(company or '').strip()).only('id','title','company','url','target_url','canonical_url','search_url','description','raw_search_snippet','role_location','country','fit_score','last_seen')[:1500]) if str(company or '').strip() else []
    candidates=exact or list(base.only('id','title','company','url','target_url','canonical_url','search_url','description','raw_search_snippet','role_location','country','fit_score','last_seen')[:2500])
    rows=[]
    for row in candidates:
        row_url=row.target_url or row.canonical_url or row.url or row.search_url
        if company_key(row.company,row_url)==ck:
            rows.append(row)
    count=len(rows)
    if count<4:
        return {'allow':True,'count':count,'reason':'below rolling company concentration threshold','anchor':None,'materially_distinct':True,'stronger_fit':False}
    max_fit=max([int(getattr(r,'fit_score',0) or 0) for r in rows] or [0])
    closest=None; closest_family=0.0; closest_body=0.0
    incoming_loc=' '.join(x for x in (role_location,country) if str(x or '').strip())
    for row in rows:
        fam=role_family_similarity(title,row.title)
        body=content_similarity(description,row.description or row.raw_search_snippet or '')
        if max(fam,body)>max(closest_family,closest_body):
            closest=row; closest_family=fam; closest_body=body
    loc_distinct=bool(closest and materially_different_location(incoming_loc,' '.join(x for x in (closest.role_location,closest.country) if str(x or '').strip())))
    materially_distinct=(closest is None) or (closest_family<0.58 and closest_body<0.38) or (loc_distinct and closest_family<0.80)
    threshold=max(int(base_fit_threshold or 0),70)
    stronger_fit=int(fit_score or 0)>=max(threshold+8,max_fit+7,82)
    if count<8:
        allow=bool(materially_distinct or stronger_fit)
        reason='rolling company concentration 4-7: require materially different role or substantially stronger fit'
    elif count<12:
        allow=bool(stronger_fit or (materially_distinct and int(fit_score or 0)>=max(threshold+5,80)))
        reason='rolling company concentration 8-11: require distinct role with solid fit, or substantially stronger fit'
    else:
        allow=bool(materially_distinct and int(fit_score or 0)>=max(threshold+12,90))
        reason='rolling company concentration 12+: require both material differentiation and high fit'
    anchor=closest or (max(rows,key=lambda r:(int(getattr(r,'fit_score',0) or 0),getattr(r,'last_seen',timezone.now()))) if rows else None)
    return {'allow':allow,'count':count,'reason':reason,'anchor':anchor,'materially_distinct':materially_distinct,'stronger_fit':stronger_fit,'max_existing_fit':max_fit,'closest_family_similarity':round(closest_family,3),'closest_content_similarity':round(closest_body,3)}

def lead_matches_opportunity(lead: CompanyLead, opp: Opportunity) -> bool:
    lead_url = lead.target_url or lead.source_url or lead.search_url
    opp_url = opp.target_url or opp.canonical_url or opp.url or opp.search_url
    ld, od = domain_key(lead_url), domain_key(opp_url)
    lc, oc = company_key(lead.company, lead_url), company_key(opp.company, opp_url)
    if ld and od and ld == od:
        return True
    return bool(lc and oc and lc == oc)


def active_opportunity_for_company(company: str, url: str = ''):
    """Return a concrete active Opportunity for this company/domain, if one exists."""
    ck, dk = company_key(company, url), domain_key(url)
    qs = Opportunity.objects.filter(user_deleted=False, suppressed=False).exclude(status='rejected').order_by('-fit_score', '-last_seen')
    # Cheap narrowing first; normalized matching below catches formatting variants.
    if company:
        narrowed = qs.filter(company__iexact=company).first()
        if narrowed:
            return narrowed
    for opp in qs.only('id','company','url','target_url','canonical_url','search_url','title')[:5000]:
        ou = opp.target_url or opp.canonical_url or opp.url or opp.search_url
        if dk and domain_key(ou) == dk:
            return opp
        if ck and company_key(opp.company, ou) == ck:
            return opp
    return None


def suppress_overlapping_leads(opp: Opportunity) -> int:
    """Non-destructive cross-list guard.

    Older releases moved Hidden Leads to the Recycle Bin as soon as a matching
    Opportunity appeared. In local/GPU discovery this caused records to flash in
    the UI and then return 404 as asynchronous qualification/dedup ran. A concrete
    Opportunity may rank above a lead in presentation, but discovery must never
    delete/recycle the other record automatically.
    """
    return 0


def active_duplicate_opportunity(title: str, company: str, url: str, *, exclude_id=None, days=180):
    """Same-role duplicate check across URL variants and a reasonable recency window."""
    since = timezone.now() - timedelta(days=max(30, int(days or 180)))
    qs = Opportunity.objects.filter(user_deleted=False, first_seen_by_portal__gte=since)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    nu, ck, tk = opportunity_identity(title, company, url)
    for row in qs.only('id','title','company','url','target_url','canonical_url','search_url','fit_score','last_seen')[:5000]:
        ru = row.target_url or row.canonical_url or row.url or row.search_url
        rnu, rck, rtk = opportunity_identity(row.title, row.company, ru)
        if nu and rnu == nu:
            return row
        if vacancy_url_key(url) and vacancy_url_key(ru) == vacancy_url_key(url):
            return row
        incoming_req=requisition_keys(url)
        row_req=requisition_keys(ru)
        if ck and rck == ck and incoming_req and row_req and not incoming_req.isdisjoint(row_req):
            return row
        # Same employer + same title alone is no longer sufficient: distinct requisition
        # IDs, locations, or responsibilities may represent separate vacancies. The
        # second-stage role-family check evaluates those richer signals after page fetch.
    return None


def active_duplicate_lead(company: str, url: str, *, exclude_id=None):
    qs = CompanyLead.objects.filter(user_deleted=False)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    ck, dk = company_key(company, url), domain_key(url)
    for row in qs.only('id','company','target_url','source_url','search_url','score','updated_at')[:5000]:
        ru = row.target_url or row.source_url or row.search_url
        if dk and domain_key(ru) == dk:
            return row
        if ck and company_key(row.company, ru) == ck:
            return row
    return None


def contact_quality(email: str, name: str = '', generic: bool | None = None) -> int:
    email = str(email or '').strip().lower()
    local = email.split('@', 1)[0] if '@' in email else ''
    compact = re.sub(r'[^a-z0-9]+', '', local)
    generic_hit = bool(generic) or compact in _GENERIC_LOCALS or any(compact.startswith(x) for x in ('jobs','careers','recruit','talent','info','hello','contact'))
    score = 35 if generic_hit else 70
    if name and not generic_hit:
        score += 20
    if re.search(r'[._-]', local) and not generic_hit:
        score += 5
    return min(100, score)


def recent_company_contact(company: str, source_url: str = '', *, days=120, exclude_email=''):
    ck, dk = company_key(company, source_url), domain_key(source_url)
    if not ck and not dk:
        return None
    since = timezone.now() - timedelta(days=max(14, int(days or 120)))
    qs = Contact.objects.filter(deleted_at__isnull=True, last_seen__gte=since).exclude(email__iexact=exclude_email).order_by('-last_seen')
    for row in qs.only('id','email','name','company','source_url','generic','confidence','last_seen')[:5000]:
        if dk and domain_key(row.source_url or row.email) == dk:
            return row
        if ck and company_key(row.company, row.source_url or row.email) == ck:
            return row
    return None


def clean_contact_name(name: str, company: str = '') -> str:
    """Keep person/salutation name independent from company; strip accidental suffixes."""
    value = ' '.join(str(name or '').split()).strip()
    comp = ' '.join(str(company or '').split()).strip()
    if not value:
        return ''
    if comp:
        low, clow = value.casefold(), comp.casefold()
        for sep in (' - ', ' — ', ' | ', ' · ', ', '):
            suffix = sep + clow
            if low.endswith(suffix):
                value = value[:len(value)-len(suffix)].strip()
                break
        if value.casefold() == clow:
            return ''
    return value[:200]


def reconcile_active_duplicates() -> dict:
    """Compatibility hook retained for callers; never mutates visible records.

    New discoveries are deduplicated before persistence. Existing records are kept
    stable so browsing a list can never make an Opportunity/Hidden Lead disappear
    or turn a previously valid detail URL into 404.
    """
    return {'opportunities_recycled':0,'hidden_leads_recycled':0}
