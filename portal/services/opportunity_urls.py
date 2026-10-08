from __future__ import annotations

import re
import urllib.parse


def _parts(url: str):
    try:
        return urllib.parse.urlsplit(str(url or '').strip())
    except Exception:
        return urllib.parse.SplitResult('', '', '', '', '')



# High-confidence adult-content domains that must never enter ScoutBox records.
# Keep this deliberately domain-focused to avoid false positives on legitimate pages.
_ADULT_HOST_MARKERS = (
    'xnxx.com', 'xvideos.com', 'pornhub.com', 'redtube.com', 'youporn.com',
    'xhamster.com', 'tube8.com', 'spankbang.com', 'onlyfans.com', 'brazzers.com',
)

def is_disallowed_adult_url(url: str) -> bool:
    p = _parts(url)
    host = (p.netloc or '').lower().removeprefix('www.')
    if not host:
        return False
    return any(host == marker or host.endswith('.' + marker) for marker in _ADULT_HOST_MARKERS)


def is_generic_opportunity_collection_url(url: str) -> bool:
    """Return True for obvious company/ATS boards that are not one concrete role.

    This deliberately targets high-confidence collection URL shapes. It is used as a
    persistence guard: discovery may use a board as evidence, but Opportunities must
    resolve to one item-level role/project URL before they are stored.
    """
    p=_parts(url); host=(p.netloc or '').lower().removeprefix('www.'); path=(p.path or '').strip('/'); segments=[x for x in path.split('/') if x]
    if not host:
        return True

    # Generic site/careers roots.
    if not segments:
        return True
    lowered='/'.join(segments).lower()
    # Common direct-company collection pages, including filename-style roots.
    if lowered in {'jobs','careers','openings','positions','vacancies','work-with-us','join-us','jobs.html','careers.html','openings.html','positions.html','vacancies.html','about/jobs','about/careers','company/jobs','company/careers'}:
        return True
    if re.search(r'(^|/)(?:jobs|careers|openings|positions|vacancies)(?:\.html?)?/?$', lowered, re.I):
        return True

    if host=='jobs.ashbyhq.com' or host.endswith('.jobs.ashbyhq.com'):
        # jobs.ashbyhq.com/<company>/<posting-id-or-slug> is an item; company root is a board.
        return len(segments) <= 1

    if host=='jobs.lever.co' or host.endswith('.jobs.lever.co'):
        # jobs.lever.co/<company>/<posting-id>
        return len(segments) <= 1

    if 'greenhouse.io' in host:
        # Common detail routes include /<company>/jobs/<id> or /embed/job_app?for=...&token=...
        query=urllib.parse.parse_qs(p.query)
        if '/jobs/' in '/'+lowered+'/' or str(query.get('token') or '').strip('[]\'"'):
            return False
        return len(segments) <= 1 or lowered.endswith('/jobs')

    if host=='apply.workable.com' or host.endswith('.apply.workable.com'):
        # apply.workable.com/<company>/j/<id>/
        return '/j/' not in '/'+lowered+'/'

    if 'smartrecruiters.com' in host:
        if host.startswith('careers.'):
            return True
        # jobs.smartrecruiters.com/<company>/<id-title>
        return len(segments) < 2

    if 'myworkdayjobs.com' in host or host.endswith('.workdayjobs.com'):
        # Workday item pages use /job/...; tenant career roots do not.
        return '/job/' not in '/'+lowered+'/'

    if 'bamboohr.com' in host and '/careers/' in '/'+lowered+'/':
        # BambooHR role URLs normally include ?id=<posting id>.
        return not bool(urllib.parse.parse_qs(p.query).get('id'))

    # Conservative generic careers/listing detection for direct company sites.
    tail=segments[-1].lower()
    if tail in {'jobs','careers','openings','positions','vacancies','jobs.html','careers.html','openings.html','positions.html','vacancies.html'} and not p.query:
        return True
    if re.search(r'/(?:jobs|careers|openings|positions)/(?:search|all|browse|list)/?$', '/'+lowered+'/', re.I):
        return True
    return False


def looks_like_specific_opportunity_url(url: str) -> bool:
    p=_parts(url)
    return p.scheme in ('http','https') and bool(p.netloc) and not is_generic_opportunity_collection_url(url)
