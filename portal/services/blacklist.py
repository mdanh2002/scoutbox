from urllib.parse import urlsplit
import re
from portal.models import SourceBlacklist
from .platforms import is_job_platform_host, is_platform_company_name

LABEL_BLACKLIST_MIN_CHARS = 7

# Hosts that represent job boards, social/job aggregators, directories, or public
# discovery surfaces rather than the hiring company itself.  Opportunity
# blacklisting must never suppress by these domains; use exact company-name rules
# instead so one bad/irrelevant row cannot hide every posting from the same board.
AGGREGATOR_BLACKLIST_DOMAINS = {
    # Public job boards and professional/social aggregators
    'linkedin.com', 'indeed.com', 'glassdoor.com', 'ziprecruiter.com', 'monster.com',
    'simplyhired.com', 'jooble.org', 'careerjet.com', 'talent.com', 'jobrapido.com',
    'jobstreet.com', 'seek.com.au', 'jobsdb.com', 'dice.com', 'careerbuilder.com',
    'wellfound.com', 'angel.co', 'builtin.com', 'remoteok.com', 'weworkremotely.com',
    'remotive.com', 'himalayas.app', 'jobicy.com', 'flexjobs.com', 'otta.com',
    'cord.co', 'sitepoint.com', 'workatastartup.com', 'ycstartupjobs.com',
    'startup.jobs', 'startupjobs.com', 'levels.fyi', 'theorg.com',
    # ATS / application hosting platforms
    'workable.com', 'greenhouse.io', 'lever.co', 'ashbyhq.com', 'smartrecruiters.com',
    'bamboohr.com', 'recruitee.com', 'comeet.com', 'jobvite.com', 'teamtailor.com',
    'icims.com', 'myworkdayjobs.com', 'workdayjobs.com', 'successfactors.com',
    'personio.com', 'pinpointhq.com', 'trakstar.com', 'jazzhr.com', 'paylocity.com',
    'ultipro.com', 'ultipro.ca', 'oraclecloud.com', 'hirebridge.com', 'applytojob.com',
    'catsone.com', 'breezy.hr', 'rippling-ats.com', 'jobsoid.com',
    'zohorecruit.com', 'join.com', 'join-lemmy.org', 'freshteam.com', 'talentreef.com',
}

AGGREGATOR_HOST_PREFIXES = (
    'jobs', 'job', 'careers', 'career', 'apply', 'boards', 'ats', 'recruiting',
    'recruitment', 'talent', 'hire', 'hiring', 'vacancies', 'opportunities',
)

COMPANY_LEGAL_SUFFIXES = {
    'inc', 'incorporated', 'llc', 'ltd', 'limited', 'gmbh', 'corp', 'corporation',
    'company', 'co', 'plc', 'ag', 'sa', 'sarl', 'bv', 'pte', 'pty', 'group',
    'holdings', 'holding', 'technologies', 'technology', 'tech', 'systems', 'solutions',
    'services', 'software', 'labs', 'international', 'worldwide', 'global',
    # Domain/company-name comparison noise. These often appear as marketing/TLD tokens
    # (Density AI -> density.io, Lemon.io -> lemon.io) and should not prevent a
    # clearly company-owned root domain from being shown as review context.
    'ai', 'io', 'com', 'net', 'org', 'app',
}

# Blacklist company-name matching must be conservative. These are true legal/entity
# suffixes only; marketing words such as "Technology", "Group" or "Global" are kept so
# unrelated companies cannot be collapsed onto the same blacklist identity.
BLACKLIST_LEGAL_SUFFIXES = {
    'inc','incorporated','llc','ltd','limited','gmbh','corp','corporation','co','company',
    'plc','ag','sa','sarl','bv','nv','pte','pty','llp','lp','oy','ab','aps','kg','kgaa',
}


_BLACKLIST_REASON_NOISE = (
    r'skip generic cold-outreach lead discovery',
    r'(?:is\s+)?not a project lead target',
    r'(?:is\s+)?not an opportunity source',
    r'(?:is\s+)?not a commercial Market Studies lead',
    r'(?:is\s+)?not as (?:the )?Hidden Lead company',
    r'(?:is\s+)?not a specialist project lead',
    r'(?:but\s+)?are not lead targets',
    r'never an opportunity source',
    r'(?:is\s+)?not job listings',
    r'use as evidence',
    r'are too noisy for opportunity discovery',
    r'advertised roles can still appear under Opportunities',
    r'(?:is\s+)?not (?:a |the )?(?:direct )?Hidden Lead(?: company)? target',
    r'suppress as a generic Hidden Lead target',
    r'Added from (?:Hidden Leads?|Opportunities|Recycle Bin)',
)


def clean_blacklist_reason(value):
    """Remove generic workflow prose from user-facing blacklist reasons."""
    text=' '.join(str(value or '').split()).strip()
    for phrase in _BLACKLIST_REASON_NOISE:
        text=re.sub(r'(?i)(?:^|(?<=[.;,:]))\s*'+phrase+r'\s*(?:[.;,:]|$)', ' ', text)
        text=re.sub(r'(?i)\b'+phrase+r'\b', ' ', text)
    text=re.sub(r'\s+([,.;:])',r'\1',text)
    text=re.sub(r'([,.;:])(?:\s*[,.;:])+',r'\1',text)
    text=re.sub(r'\s+',' ',text).strip(' ,;:')
    # Blacklist reasons are compact labels in list views, not prose sentences. Keep
    # meaningful punctuation such as ?/! but never retain/add a trailing full stop.
    return text.rstrip().rstrip('.').rstrip()


def normalize_pattern(value):
    raw=(value or '').strip().lower()
    if not raw:
        return ''
    if '://' in raw:
        p=urlsplit(raw)
        raw=(p.netloc+p.path).strip('/')
    raw=raw.removeprefix('www.').strip().strip('/')
    return raw[:255]


def blacklist_pattern_host(value):
    raw=normalize_pattern(value)
    return raw.split('/', 1)[0].removeprefix('www.') if raw else ''


def registrable_domain(value):
    """Return a stable display root for common domains.

    This intentionally uses a light-weight suffix heuristic instead of an external
    public-suffix dependency; it is only used as review context in blacklist dialogs.
    The backend still blacklists by company name only for Opportunities/Hidden Leads.
    """
    host=blacklist_pattern_host(value)
    if not host:
        return ''
    parts=[p for p in host.split('.') if p]
    if len(parts) <= 2:
        return host
    two_part_suffixes={
        'co.uk','org.uk','ac.uk','gov.uk','com.au','net.au','org.au','co.nz','com.sg',
        'com.hk','com.br','com.mx','com.tr','co.jp','com.cn','com.tw','co.kr','co.in',
    }
    suffix='.'.join(parts[-2:])
    if suffix in two_part_suffixes and len(parts) >= 3:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def _company_domain_key(value):
    text=str(value or '').casefold()
    text=re.sub(r'&', ' and ', text)
    tokens=[t for t in re.split(r'[^a-z0-9]+', text) if t]
    tokens=[t for t in tokens if t not in COMPANY_LEGAL_SUFFIXES]
    return ''.join(tokens), tokens


def is_company_specific_domain(domain, company):
    """True only when a domain looks owned by this specific company.

    Aggregator/ATS/job-board hosts always return False, including their subdomains.
    Company/domain matching is deliberately tolerant of spaces, punctuation, legal
    suffixes and common career subdomains, but requires a real company-token match.
    """
    root=registrable_domain(domain)
    if not root or is_aggregator_blacklist_domain(root):
        return False
    company_key,tokens=_company_domain_key(company)
    if not company_key or not tokens:
        return False
    stem=root.split('.',1)[0]
    stem_key,_=_company_domain_key(stem)
    if not stem_key:
        return False
    if stem_key == company_key or stem_key in company_key or company_key in stem_key:
        return True
    strong=[t for t in tokens if len(t) >= 4]
    if strong and any(t in stem_key for t in strong):
        return True
    compact_tokens=[t for t in tokens if len(t) >= 2]
    if len(compact_tokens) >= 2 and sum(1 for t in compact_tokens if t in stem_key) >= 2:
        return True
    return False


def company_specific_blacklist_review_domain(url_or_domain, company):
    """Domain review value for blacklist dialogs.

    Returns an empty string for job boards, ATS/aggregators, generic hosts, and domains
    that do not look company-owned.  Returned values are review-only; the actual
    blacklist rule should use the company name.
    """
    root=registrable_domain(url_or_domain)
    if not root:
        return ''
    return root if is_company_specific_domain(root, company) else ''


def _record_value(record, key, default=''):
    try:
        if isinstance(record, dict):
            return record.get(key, default)
        return getattr(record, key, default)
    except Exception:
        return default


def _append_blacklist_domain_candidate(candidates, value):
    raw=str(value or '').strip()
    if raw and raw not in candidates:
        candidates.append(raw)


def _walk_company_domain_hints(node, candidates, depth=0):
    """Collect likely company-owned URL/domain hints from retained research data.

    The popup must not depend only on the listing URL.  Some records are discovered
    through LinkedIn/SitePoint/ATS pages while ScoutBox's company research or domain-age
    badge already has the real company domain (for example Density AI -> density.io).
    Keep this hint collector conservative: only company/domain/homepage/website-like
    keys are considered, and every candidate still passes the aggregator + company-token
    checks before it is shown.
    """
    if depth > 5 or len(candidates) >= 30:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            k=str(key or '').casefold().replace('-', '_')
            if isinstance(value, (dict, list, tuple)):
                _walk_company_domain_hints(value, candidates, depth+1)
                continue
            if any(token in k for token in ('domain_age_domain','company_domain','employer_domain','homepage','home_page','website','site_url','company_url','employer_url','public_url')):
                _append_blacklist_domain_candidate(candidates, value)
    elif isinstance(node, (list, tuple)):
        for child in list(node)[:60]:
            _walk_company_domain_hints(child, candidates, depth+1)


def _record_domain_candidates(record):
    candidates=[]
    for data_key in ('company_intel', 'extracted_facts'):
        data=_record_value(record, data_key, {})
        if isinstance(data, dict):
            structured=data.get('structured') if isinstance(data.get('structured'), dict) else {}
            for key in ('domain_age_domain','company_domain','employer_domain','homepage','website','website_url','company_url','employer_url'):
                _append_blacklist_domain_candidate(candidates, structured.get(key))
                _append_blacklist_domain_candidate(candidates, data.get(key))
            _walk_company_domain_hints(data, candidates)
    for key in ('target_url', 'canonical_url', 'url', 'source_url', 'contact_url', 'search_url'):
        _append_blacklist_domain_candidate(candidates, _record_value(record, key, ''))
    return candidates


def safe_record_blacklist_domain(record):
    """First non-aggregator domain available on a record for explicit domain-only blocking."""
    for candidate in _record_domain_candidates(record):
        root=registrable_domain(candidate)
        if root and not is_aggregator_blacklist_domain(root):
            return root
    return ''


def company_specific_blacklist_review_domain_for_record(record):
    """Best company-domain review value for Opportunity/Hidden Lead blacklist modals.

    Prefer explicit company-research/domain-age hints before raw listing URLs.  That
    lets real domains shown elsewhere in the list (such as density.io for Density AI)
    appear in the review dialog while third-party job boards and ATS hosts remain blank.
    """
    company=str(_record_value(record, 'company', '') or '').strip()
    candidates=_record_domain_candidates(record)
    if company:
        for candidate in candidates:
            domain=company_specific_blacklist_review_domain(candidate, company)
            if domain:
                return domain
    # Hidden Leads may have no usable company name yet but still have a safe company-owned domain.
    return safe_record_blacklist_domain(record)


def company_blacklist_candidate(record):
    """Return a validated company-name-only blacklist candidate for a record.

    Short company names are accepted only when ScoutBox has a plausible company-owned
    domain to anchor the identity. Platform/aggregator labels are never accepted.
    """
    company=re.sub(r'\s+',' ',str(_record_value(record,'company','') or '')).strip()[:255]
    domain=company_specific_blacklist_review_domain_for_record(record)
    if not company or is_platform_company_name(company):
        return {'valid':False,'company':company,'domain':domain,'reason':'No usable company name.'}
    allow_short=bool(domain)
    if not valid_company_blacklist_label(company,allow_short=allow_short):
        reason=(f'Company names shorter than {LABEL_BLACKLIST_MIN_CHARS} characters require a verified company domain.' if len(normalize_label(company))<LABEL_BLACKLIST_MIN_CHARS else 'Company name is not safe to blacklist.')
        return {'valid':False,'company':company,'domain':domain,'reason':reason}
    return {'valid':True,'company':company,'domain':domain,'reason':''}


def blacklist_candidate_for_record(record, *, allow_domain_only=False):
    """Validated blacklist candidate; optionally permits domain-only records."""
    company_candidate=company_blacklist_candidate(record)
    if company_candidate.get('valid'):
        company_candidate['use_domain']=False
        return company_candidate
    domain=company_candidate.get('domain') or safe_record_blacklist_domain(record)
    if allow_domain_only and domain and not is_aggregator_blacklist_domain(domain):
        return {'valid': True, 'company': '', 'domain': domain, 'use_domain': True, 'reason': ''}
    if domain:
        company_candidate['domain']=domain
    return company_candidate


def is_aggregator_blacklist_domain(value):
    host=blacklist_pattern_host(value)
    if not host:
        return False
    # 0.10.90: one shared classifier is authoritative across discovery, research
    # and blacklisting.  This closes registry drift such as BuiltIn being blocked
    # here but accidentally treated as an employer elsewhere.
    if is_job_platform_host(host):
        return True
    root=registrable_domain(host)
    host_left=host.split('.', 1)[0]
    if host_left in AGGREGATOR_HOST_PREFIXES and root != host:
        # Subdomains such as jobs.linkedin.com, boards.foo-ats.com or apply.example-ats.io
        # are treated as non-company-owned review domains unless the root is later
        # proven to match the company by is_company_specific_domain().
        pass
    for domain in AGGREGATOR_BLACKLIST_DOMAINS:
        d=blacklist_pattern_host(domain)
        rd=registrable_domain(d)
        if host == d or host.endswith('.' + d) or root == d or root == rd:
            return True
    # Loose ATS/job-board signal matching for mild platform variations.
    loose_signals=(
        'greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters', 'recruitee',
        'bamboohr', 'jobvite', 'teamtailor', 'icims', 'myworkdayjobs', 'workdayjobs',
        'successfactors', 'personio', 'pinpointhq', 'jazzhr', 'hirebridge', 'applytojob',
        'zohorecruit', 'freshteam', 'talentreef', 'himalayas', 'remoteok', 'wellfound',
        'linkedin', 'indeed', 'glassdoor', 'ziprecruiter', 'sitepoint',
    )
    compact=re.sub(r'[^a-z0-9]+', '', host.casefold())
    return any(signal in compact for signal in loose_signals)



def normalize_label(value):
    raw=re.sub(r'\s+', ' ', str(value or '')).strip().casefold()
    return raw[:255]


def normalize_company_blacklist_key(value):
    """Normalize safe legal-name variants without fuzzy/sub-string matching.

    Example: ``Canonical``, ``Canonical Ltd`` and ``Canonical Limited`` share a key,
    while ``Canonical Systems`` remains a distinct company identity.
    """
    text=str(value or '').casefold().replace('&',' and ')
    tokens=[t for t in re.split(r'[^a-z0-9]+',text) if t]
    while tokens and tokens[-1] in BLACKLIST_LEGAL_SUFFIXES:
        tokens.pop()
    return ' '.join(tokens)[:255]


def valid_label_only_pattern(label):
    return len(normalize_label(label)) >= LABEL_BLACKLIST_MIN_CHARS


def valid_company_blacklist_label(label, *, allow_short=False):
    text=re.sub(r'\s+', ' ', str(label or '')).strip()
    key=text.casefold()
    if not text or is_platform_company_name(text):
        return False
    if not allow_short and len(normalize_label(text)) < LABEL_BLACKLIST_MIN_CHARS:
        return False
    if len(text) > 80:
        return False
    noisy_tokens=(
        'http://','https://','www.',' applicants',' applicant','posted ',' posted',' ago',
        'job closed','closed job','hiring now','apply now','채용공고','지원자','개월 전','에서 이 자리',
    )
    return not any(token in key for token in noisy_tokens)


def url_key(url):
    try:
        p=urlsplit(url or '')
        host=(p.netloc or '').lower().removeprefix('www.')
        path=(p.path or '').lower().strip('/')
        return host + (('/'+path) if path else '')
    except Exception:
        return ''


def matches(pattern, url):
    pat=normalize_pattern(pattern); key=url_key(url)
    if not pat or not key:
        return False
    if '/' in pat:
        return key == pat or key.startswith(pat.rstrip('/') + '/')
    host=key.split('/',1)[0]
    return host == pat or host.endswith('.'+pat)


def _scope_matches(row_scope, requested_scope):
    row_scope=(row_scope or 'all').strip() or 'all'
    requested_scope=(requested_scope or 'all').strip() or 'all'
    if row_scope=='all' or requested_scope=='all':
        return True
    return row_scope==requested_scope


def _label_only_match(row, company):
    if getattr(row, 'domain', ''):
        return False
    label=normalize_company_blacklist_key(getattr(row, 'label', '') or '')
    company_key=normalize_company_blacklist_key(company)
    return bool(label and company_key and label == company_key and valid_company_blacklist_label(company,allow_short=True))


def is_blacklisted_company(company, scope='all'):
    """Return a label-only blacklist row for the same canonical company identity."""
    if not valid_company_blacklist_label(company,allow_short=True):
        return None
    qs=SourceBlacklist.objects.filter(enabled=True,deleted_at__isnull=True,domain='').only('domain','label','scope')
    for row in qs:
        if _scope_matches(getattr(row,'scope','all'),scope) and _label_only_match(row, company):
            return row
    return None


def is_blacklisted_url(url, scope='all', company=None):
    """Return the matching blacklist row for this discovery surface.

    Domain/URL entries match the canonical URL as before.  Label-only entries have an
    empty domain and match only an exact normalized company name of at least seven
    characters, so they can suppress canonical companies with noisy hiring processes
    without accidentally blocking short/generic labels.
    """
    qs=SourceBlacklist.objects.filter(enabled=True,deleted_at__isnull=True).only('domain','label','scope')
    for row in qs:
        if not _scope_matches(getattr(row,'scope','all'),scope):
            continue
        domain=(getattr(row,'domain','') or '').strip()
        # Never let a job-board / aggregator host suppress Opportunities.  A
        # company label-only rule may still match below.
        if domain and scope == 'opportunities' and is_aggregator_blacklist_domain(domain):
            continue
        if domain and matches(domain,url):
            return row
        if not domain and company is not None and _label_only_match(row, company):
            return row
    return None


def pattern_for_url(url):
    try:
        return (urlsplit(url).netloc or '').lower().removeprefix('www.')[:255]
    except Exception:
        return ''


# (domain, label, reason, scope)
DEFAULT_BLACKLIST = [
    ('wikipedia.org', 'Wikipedia', 'Reference/encyclopedia content; not an opportunity source.', 'all'),
    ('en.wikipedia.org', 'Wikipedia', 'Reference/encyclopedia content; not an opportunity source.', 'all'),
    ('learn.microsoft.com', 'Microsoft Learn', 'Technical documentation.', 'all'),
    ('msdn.microsoft.com', 'MSDN', 'Technical documentation/archive.', 'all'),
    ('docs.microsoft.com', 'Microsoft Docs', 'Technical documentation.', 'all'),
    ('developer.mozilla.org', 'MDN', 'Technical documentation.', 'all'),
    ('docs.python.org', 'Python Docs', 'Technical documentation.', 'all'),
    ('docs.oracle.com', 'Oracle Docs', 'Technical documentation.', 'all'),
    ('docs.github.com', 'GitHub Docs', 'Technical documentation.', 'all'),
    ('support.google.com', 'Google Help', 'Support/documentation content.', 'all'),
    ('cloud.google.com/docs', 'Google Cloud Docs', 'Technical documentation.', 'all'),
    ('docs.aws.amazon.com', 'AWS Docs', 'Technical documentation.', 'all'),
    ('developer.apple.com/documentation', 'Apple Developer Docs', 'Technical documentation.', 'all'),
    ('man7.org', 'Linux man-pages', 'Technical manual content.', 'all'),
    ('kernel.org', 'Linux kernel project', 'Kernel project/reference content; not a commercial lead.', 'all'),
    ('arm.com', 'Arm', 'Vendor/community/support content is excluded from Hidden Leads discovery.', 'all'),
    ('r-project.org', 'R Project manuals', 'Technical/manual content, not job listings.', 'all'),
    ('cran.r-project.org', 'CRAN', 'Package/manual content, not job listings.', 'all'),
    ('youtube.com', 'YouTube', 'Video/media pages are too noisy for opportunity discovery.', 'all'),
    ('music.youtube.com', 'YouTube Music', 'Media content; never an opportunity source.', 'all'),
    # Large employers can still surface interesting advertised roles. They are excluded
    # only from cold-contact/Hidden Leads discovery by default.
    ('amazon.com', 'Amazon', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('microsoft.com', 'Microsoft', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('google.com', 'Google', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('apple.com', 'Apple', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('meta.com', 'Meta', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('nvidia.com', 'NVIDIA', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('intel.com', 'Intel', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('oracle.com', 'Oracle', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('ibm.com', 'IBM', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('cisco.com', 'Cisco', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('qualcomm.com', 'Qualcomm', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('samsung.com', 'Samsung', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('broadcom.com', 'Broadcom', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('amd.com', 'AMD', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('dell.com', 'Dell', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    ('hp.com', 'HP', 'Large employer: skip generic cold-outreach lead discovery; advertised roles can still appear under Opportunities.', 'hidden_leads'),
    # Hidden Lead noise controls. These domains may still be useful as search/reference
    # sources or advertised Opportunities; they are poor cold-outreach targets themselves.
    ('cloudflare.com', 'Cloudflare', 'Large infrastructure vendor; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('salesforce.com', 'Salesforce', 'Large enterprise software vendor; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('adobe.com', 'Adobe', 'Large software vendor; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('sap.com', 'SAP', 'Large enterprise software vendor; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('vmware.com', 'VMware', 'Large enterprise virtualization vendor; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('atlassian.com', 'Atlassian', 'Large software vendor; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('shopify.com', 'Shopify', 'Large technology company; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('uber.com', 'Uber', 'Large technology company; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('airbnb.com', 'Airbnb', 'Large technology company; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('netflix.com', 'Netflix', 'Large technology company; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('tesla.com', 'Tesla', 'Large employer; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('huawei.com', 'Huawei', 'Large technology vendor; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('tencent.com', 'Tencent', 'Large technology company; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('alibaba.com', 'Alibaba', 'Large technology company; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('bytedance.com', 'ByteDance', 'Large technology company; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('sony.com', 'Sony', 'Large multinational; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('panasonic.com', 'Panasonic', 'Large multinational; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('bosch.com', 'Bosch', 'Large multinational; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('siemens.com', 'Siemens', 'Large multinational; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('honeywell.com', 'Honeywell', 'Large multinational; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('gm.com', 'General Motors', 'Large employer; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('generalmotors.com', 'General Motors', 'Large employer; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('ford.com', 'Ford', 'Large employer; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('stellantis.com', 'Stellantis', 'Large employer; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('boeing.com', 'Boeing', 'Large employer; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('lockheedmartin.com', 'Lockheed Martin', 'Large employer; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('northropgrumman.com', 'Northrop Grumman', 'Large employer; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('rtx.com', 'RTX', 'Large employer; suppress as a generic Hidden Lead target.', 'hidden_leads'),
    ('wikihow.com', 'wikiHow', 'How-to/reference publisher, not a specialist project lead.', 'hidden_leads'),
    ('howstuffworks.com', 'HowStuffWorks', 'Reference publisher, not a specialist project lead.', 'hidden_leads'),
    ('techtarget.com', 'TechTarget', 'Reference/publisher content, not a project lead target.', 'hidden_leads'),
    ('techopedia.com', 'Techopedia', 'Reference/publisher content, not a project lead target.', 'hidden_leads'),
    ('geeksforgeeks.org', 'GeeksforGeeks', 'Tutorial/reference content, not a project lead target.', 'hidden_leads'),
    ('tutorialspoint.com', 'TutorialsPoint', 'Tutorial/reference content, not a project lead target.', 'hidden_leads'),
    ('w3schools.com', 'W3Schools', 'Tutorial/reference content, not a project lead target.', 'hidden_leads'),
    ('computerhope.com', 'Computer Hope', 'Reference/help content, not a project lead target.', 'hidden_leads'),
    ('lifewire.com', 'Lifewire', 'Consumer/reference publisher, not a specialist project lead.', 'hidden_leads'),
    ('makeuseof.com', 'MakeUseOf', 'How-to publisher, not a specialist project lead.', 'hidden_leads'),
    ('stackoverflow.com', 'Stack Overflow', 'Q&A platform; use as evidence, not a Hidden Lead target.', 'hidden_leads'),
    ('stackexchange.com', 'Stack Exchange', 'Q&A platform; use as evidence, not a Hidden Lead target.', 'hidden_leads'),
    ('superuser.com', 'Super User', 'Q&A platform; not a Hidden Lead target.', 'hidden_leads'),
    ('serverfault.com', 'Server Fault', 'Q&A platform; not a Hidden Lead target.', 'hidden_leads'),
    ('quora.com', 'Quora', 'Q&A publisher; not a Hidden Lead target.', 'hidden_leads'),
    ('medium.com', 'Medium', 'Publishing platform; articles may be evidence but are not lead targets.', 'hidden_leads'),
    ('dev.to', 'DEV Community', 'Publishing/community platform; not a direct Hidden Lead target.', 'hidden_leads'),
    ('hashnode.com', 'Hashnode', 'Publishing platform; not a direct Hidden Lead target.', 'hidden_leads'),
    ('readthedocs.io', 'Read the Docs', 'Documentation hosting; not a Hidden Lead target.', 'hidden_leads'),
    ('readthedocs.org', 'Read the Docs', 'Documentation hosting; not a Hidden Lead target.', 'hidden_leads'),
    ('docs.rs', 'docs.rs', 'Package documentation; not a Hidden Lead target.', 'hidden_leads'),
    ('pkg.go.dev', 'Go Packages', 'Package documentation; not a Hidden Lead target.', 'hidden_leads'),
    ('pypi.org', 'PyPI', 'Package index; not a Hidden Lead target.', 'hidden_leads'),
    ('npmjs.com', 'npm', 'Package index; not a Hidden Lead target.', 'hidden_leads'),
    ('crates.io', 'crates.io', 'Package index; not a Hidden Lead target.', 'hidden_leads'),
    ('developer.android.com', 'Android Developers', 'Technical documentation; not a Hidden Lead target.', 'hidden_leads'),
    ('docs.docker.com', 'Docker Docs', 'Technical documentation; not a Hidden Lead target.', 'hidden_leads'),
    ('kubernetes.io/docs', 'Kubernetes Docs', 'Technical documentation; not a Hidden Lead target.', 'hidden_leads'),
    ('manpages.ubuntu.com', 'Ubuntu Manpages', 'Technical manuals; not a Hidden Lead target.', 'hidden_leads'),
    ('sourceforge.net', 'SourceForge', 'Download/project hosting; not a direct Hidden Lead target.', 'hidden_leads'),
    ('softpedia.com', 'Softpedia', 'Software/download publisher; not a Hidden Lead target.', 'hidden_leads'),
    ('filehippo.com', 'FileHippo', 'Software/download publisher; not a Hidden Lead target.', 'hidden_leads'),
    ('alternativeto.net', 'AlternativeTo', 'Software directory; not a direct Hidden Lead target.', 'hidden_leads'),
    ('slant.co', 'Slant', 'Recommendation directory; not a direct Hidden Lead target.', 'hidden_leads'),
    ('linkedin.com', 'LinkedIn', 'Job/social platform; use for discovery evidence, not as the Hidden Lead company.', 'hidden_leads'),
    ('indeed.com', 'Indeed', 'Job aggregator; not a Hidden Lead company target.', 'hidden_leads'),
    ('glassdoor.com', 'Glassdoor', 'Job/company aggregator; not a Hidden Lead company target.', 'hidden_leads'),
    ('ziprecruiter.com', 'ZipRecruiter', 'Job aggregator; not a Hidden Lead company target.', 'hidden_leads'),
    ('monster.com', 'Monster', 'Job aggregator; not a Hidden Lead company target.', 'hidden_leads'),
    ('simplyhired.com', 'SimplyHired', 'Job aggregator; not a Hidden Lead company target.', 'hidden_leads'),
    ('jooble.org', 'Jooble', 'Job aggregator; not a Hidden Lead company target.', 'hidden_leads'),
    ('careerjet.com', 'Careerjet', 'Job aggregator; not a Hidden Lead company target.', 'hidden_leads'),
    ('talent.com', 'Talent.com', 'Job aggregator; not a Hidden Lead company target.', 'hidden_leads'),
    ('jobrapido.com', 'Jobrapido', 'Job aggregator; not a Hidden Lead company target.', 'hidden_leads'),
    ('jobstreet.com', 'JobStreet', 'Job board; not a Hidden Lead company target.', 'hidden_leads'),
    ('seek.com.au', 'SEEK', 'Job board; not a Hidden Lead company target.', 'hidden_leads'),
    ('jobsdb.com', 'JobsDB', 'Job board; not a Hidden Lead company target.', 'hidden_leads'),
    ('crunchbase.com', 'Crunchbase', 'Company directory; use as evidence, not as the Hidden Lead target.', 'hidden_leads'),
    ('zoominfo.com', 'ZoomInfo', 'Company/contact directory; not a Hidden Lead target.', 'hidden_leads'),
    ('rocketreach.co', 'RocketReach', 'Contact directory; not a Hidden Lead target.', 'hidden_leads'),
    ('apollo.io', 'Apollo', 'Contact/sales directory; not a Hidden Lead target.', 'hidden_leads'),
    ('signalhire.com', 'SignalHire', 'Contact directory; not a Hidden Lead target.', 'hidden_leads'),
    ('contactout.com', 'ContactOut', 'Contact directory; not a Hidden Lead target.', 'hidden_leads'),
    ('facebook.com', 'Facebook', 'Social platform; not a direct Hidden Lead company target.', 'hidden_leads'),
    ('instagram.com', 'Instagram', 'Social platform; not a direct Hidden Lead company target.', 'hidden_leads'),
    ('pinterest.com', 'Pinterest', 'Social platform; not a direct Hidden Lead company target.', 'hidden_leads'),
    ('tiktok.com', 'TikTok', 'Social platform; not a direct Hidden Lead company target.', 'hidden_leads'),
    ('x.com', 'X', 'Social platform; not a direct Hidden Lead company target.', 'hidden_leads'),
    ('twitter.com', 'Twitter', 'Social platform; not a direct Hidden Lead company target.', 'hidden_leads'),
]

# Keep every shipped reason in the same compact list-label form used by manual edits.
# This also guarantees newly reset defaults never re-introduce a trailing full stop.
DEFAULT_BLACKLIST=[(domain,label,clean_blacklist_reason(reason),scope) for domain,label,reason,scope in DEFAULT_BLACKLIST]


def reset_defaults():
    # Reset the active list to shipped defaults without destroying unrelated items that
    # the user intentionally left in the Recycle Bin. A recycled shipped-default domain
    # is restored because the reset explicitly asks for the built-in defaults again.
    shipped={normalize_pattern(domain):(label,clean_blacklist_reason(reason),scope) for domain,label,reason,scope in DEFAULT_BLACKLIST}
    SourceBlacklist.objects.filter(deleted_at__isnull=True).exclude(domain__in=list(shipped)).delete()
    for domain,(label,reason,scope) in shipped.items():
        SourceBlacklist.objects.update_or_create(
            domain=domain,
            defaults={'label':label,'reason':reason,'scope':scope,'enabled':True,'built_in':True,'deleted_at':None},
        )


def _record_urls(record, fields):
    """Yield distinct non-empty URL values from the requested record fields."""
    seen=set()
    for field in fields:
        value=(getattr(record,field,'') or '').strip()
        if value and value not in seen:
            seen.add(value)
            yield value


def matching_blacklist_for_record(record, scope):
    """Return the first active blacklist row matching any canonical URL on a record."""
    if scope=='opportunities':
        fields=('target_url','canonical_url','url','search_url')
    elif scope=='hidden_leads':
        fields=('target_url','source_url','search_url')
    else:
        fields=('target_url','canonical_url','url','source_url','search_url')
    company=(getattr(record,'company','') or '').strip()
    for url in _record_urls(record,fields):
        row=is_blacklisted_url(url,scope=scope,company=company)
        if row:
            return row,url
    row=is_blacklisted_company(company,scope=scope)
    if row:
        return row,company
    return None,None


def enforce_active_blacklist():
    """Apply the current blacklist to records that already exist in ScoutBox.

    Discovery-time checks stop new blocked URLs from being persisted, but a user can
    add a domain to the blacklist after records have already been saved.  Keep the
    visible Opportunity/Hidden Lead inventories consistent immediately by suppressing
    those existing rows too.  This function is intentionally one-way: removing a
    blacklist rule does not silently restore records the user previously blocked.
    """
    from django.utils import timezone
    from portal.models import Opportunity, CompanyLead, Application

    now=timezone.now()
    opportunity_count=0
    lead_count=0

    for row in Opportunity.objects.filter(suppressed=False,user_deleted=False).iterator():
        blocked,blocked_url=matching_blacklist_for_record(row,'opportunities')
        if not blocked:
            continue
        block_label=(blocked.domain or blocked.label or 'company-name rule')
        reason=f'Blocked by blacklist: {block_label}'
        Opportunity.objects.filter(pk=row.pk,suppressed=False,user_deleted=False).update(
            suppressed=True,
            user_deleted=True,
            deleted_at=now,
            is_read=True,
            rejection_reason=reason,
            updated_at=now,
        )
        # Keep an associated Application/Outreach recoverable together with the
        # blacklisted Opportunity instead of silently orphaning it outside Recycle Bin.
        Application.objects.filter(opportunity_id=row.pk,deleted_at__isnull=True).update(deleted_at=now,is_read=True)
        opportunity_count+=1

    for row in CompanyLead.objects.filter(user_deleted=False).iterator():
        blocked,blocked_url=matching_blacklist_for_record(row,'hidden_leads')
        if not blocked:
            continue
        CompanyLead.objects.filter(pk=row.pk,user_deleted=False).update(
            user_deleted=True,
            deleted_at=now,
            is_read=True,
            updated_at=now,
        )
        lead_count+=1

    return {'opportunities':opportunity_count,'hidden_leads':lead_count}
