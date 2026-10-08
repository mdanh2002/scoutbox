"""Known worldwide domain variants for job/career sources.

This expands coverage in the background without adding campaign-localization UI or
changing the search-provider locale. Default/global domains remain first and all
results are deduplicated by callers.
"""
from __future__ import annotations

from urllib.parse import urlsplit

_SOURCE_DOMAIN_VARIANTS = {
    # Job boards / career sites.
    'indeed.com': (
        'indeed.com', 'sg.indeed.com', 'uk.indeed.com', 'ca.indeed.com', 'au.indeed.com',
        'ie.indeed.com', 'in.indeed.com', 'hk.indeed.com', 'nz.indeed.com', 'ph.indeed.com',
        'my.indeed.com', 'za.indeed.com', 'ae.indeed.com',
    ),
    'glassdoor.com': ('glassdoor.com', 'glassdoor.sg', 'glassdoor.co.uk', 'glassdoor.ca', 'glassdoor.com.au', 'glassdoor.co.in'),
    'jobstreet.com': ('jobstreet.com', 'sg.jobstreet.com', 'my.jobstreet.com', 'ph.jobstreet.com', 'id.jobstreet.com'),
    'jobsdb.com': ('jobsdb.com', 'hk.jobsdb.com', 'th.jobsdb.com', 'sg.jobsdb.com'),
    'seek.com.au': ('seek.com.au', 'seek.co.nz'),
    'workopolis.com': ('workopolis.com',),
    'himalayas.app': ('himalayas.app',),
    'jobicy.com': ('jobicy.com',),
    'wellfound.com': ('wellfound.com',),
    'remoteok.com': ('remoteok.com',),
    'weworkremotely.com': ('weworkremotely.com',),
    'remotive.com': ('remotive.com',),
    'linkedin.com': ('linkedin.com',),
    # ATS / direct-adapter families.  These are domain variants, not invented APIs.
    'lever.co': ('jobs.lever.co', 'jobs.eu.lever.co'),
    'jobs.lever.co': ('jobs.lever.co', 'jobs.eu.lever.co'),
    'greenhouse.io': ('boards.greenhouse.io', 'job-boards.greenhouse.io', 'boards-api.greenhouse.io'),
    'ashbyhq.com': ('jobs.ashbyhq.com', 'api.ashbyhq.com'),
    'smartrecruiters.com': ('jobs.smartrecruiters.com', 'api.smartrecruiters.com'),
}

# Only endpoints that the source itself documents/supports belong here.  Most direct
# adapters have one global API and therefore intentionally have a single endpoint.
_DIRECT_ENDPOINT_VARIANTS = {
    'lever': (
        'https://api.lever.co/v0/postings',
        'https://api.eu.lever.co/v0/postings',
    ),
    'greenhouse': ('https://boards-api.greenhouse.io/v1/boards',),
    'ashby': ('https://api.ashbyhq.com/posting-api/job-board',),
    'smartrecruiters': ('https://api.smartrecruiters.com/v1/companies',),
    'jobicy': ('https://jobicy.com/api/v2/remote-jobs',),
    'himalayas': ('https://himalayas.app/jobs/api/search',),
    'remoteok': ('https://remoteok.com/api',),
    'remotive': ('https://remotive.com/api/remote-jobs',),
}



def normalize_source_domain(value: str) -> str:
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    if '://' in raw:
        try:
            raw = urlsplit(raw).hostname or raw
        except Exception:
            pass
    return raw.strip('/').split('/', 1)[0].split(':', 1)[0].removeprefix('www.')


def _base_domain(domain: str) -> str:
    domain = normalize_source_domain(domain)
    parts = [p for p in domain.split('.') if p]
    if len(parts) <= 2:
        return domain
    two_part_suffixes = {'co.uk','com.au','co.nz','com.sg','com.hk','co.in','com.br','com.mx','co.jp','com.cn'}
    suffix = '.'.join(parts[-2:])
    if suffix in two_part_suffixes and len(parts) >= 3:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def expand_source_domains(domain: str, *, limit: int = 8) -> list[str]:
    """Return known variants for a source domain with the requested domain first."""
    original = normalize_source_domain(domain)
    if not original:
        return []
    base = _base_domain(original)
    variants = _SOURCE_DOMAIN_VARIANTS.get(original) or _SOURCE_DOMAIN_VARIANTS.get(base)
    if not variants:
        # A campaign can start from any member of a known worldwide family (for
        # example seek.co.nz or glassdoor.sg), not only the map's default key.
        # Recognize membership so the same family is expanded in either direction.
        for family in _SOURCE_DOMAIN_VARIANTS.values():
            normalized={normalize_source_domain(item) for item in family}
            if original in normalized or base in normalized:
                variants=family
                break
    variants = list(variants or (original,))
    ordered = [original] + [v for v in variants if normalize_source_domain(v) != original]
    out, seen = [], set()
    for item in ordered:
        cleaned = normalize_source_domain(item)
        if cleaned and cleaned not in seen:
            seen.add(cleaned); out.append(cleaned)
        if len(out) >= max(1, int(limit or 8)):
            break
    return out


def direct_endpoint_variants(adapter: str, default_endpoint: str = '', *, limit: int = 3) -> list[str]:
    """Return bounded, provider-supported direct endpoint variants.

    The caller's known/default endpoint stays first.  Sources with one global API simply
    return one endpoint; no country endpoint is guessed from the domain map.
    """
    key=str(adapter or '').strip().casefold()
    configured=list(_DIRECT_ENDPOINT_VARIANTS.get(key) or ())
    requested=str(default_endpoint or '').strip().rstrip('/')
    ordered=([requested] if requested else []) + [str(x).strip().rstrip('/') for x in configured]
    out=[]; seen=set()
    for endpoint in ordered:
        if not endpoint or endpoint in seen:
            continue
        seen.add(endpoint); out.append(endpoint)
        if len(out) >= max(1,int(limit or 3)):
            break
    return out


def expand_many_source_domains(domains, *, per_source_limit: int = 8, total_limit: int = 40) -> list[str]:
    out, seen = [], set()
    for domain in domains or []:
        for variant in expand_source_domains(domain, limit=per_source_limit):
            if variant not in seen:
                seen.add(variant); out.append(variant)
            if len(out) >= max(1, int(total_limit or 40)):
                return out
    return out
