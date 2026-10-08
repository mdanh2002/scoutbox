"""Deterministic role/opportunity page classification.

Search-query overlap is only a discovery hint.  A result becomes an Opportunity only
when the page itself contains evidence of an actionable role/engagement.  Relevant
technical pages without a hiring/engagement signal belong in Hidden Market instead.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

ROLE_TITLE_TERMS = (
    'engineer', 'developer', 'programmer', 'architect', 'consultant', 'contractor',
    'freelancer', 'specialist', 'technician', 'researcher', 'scientist', 'analyst',
    'administrator', 'writer', 'author', 'trainer', 'instructor', 'manager', 'lead',
    'designer', 'maintainer', 'intern', 'apprentice',
)

STRONG_ROLE_PHRASES = (
    'apply now', 'apply for this job', 'submit your application', 'submit application',
    'send your cv', 'send your resume', 'send us your cv', 'send us your resume',
    'we are hiring', "we're hiring", 'now hiring', 'join our team', 'join the team',
    'we are looking for', "we're looking for", 'we are seeking', "we're seeking",
    'job description', 'employment type', 'work authorization', 'equal opportunity employer',
)

ROLE_SECTION_PHRASES = (
    'responsibilities', 'requirements', 'qualifications', 'what you will do',
    "what you'll do", 'what we are looking for', "what we're looking for", 'about the role',
    'the position', 'your role', 'preferred qualifications', 'minimum qualifications',
    'compensation', 'salary range', 'benefits', 'what we offer',
)

NON_ROLE_TITLE_PHRASES = (
    'documentation', 'user guide', 'installation guide', 'administration guide',
    'reference manual', 'api reference', 'developer guide', 'getting started',
    'release notes', 'changelog', 'table of contents', 'manual', 'tutorial',
)

NON_ROLE_URL_PARTS = (
    '/docs/', '/documentation/', '/manual/', '/manuals/', '/guide/', '/guides/',
    '/reference/', '/api-docs/', '/apidocs/', '/wiki/', '/changelog', '/release-notes',
)

DOC_BODY_PHRASES = (
    'table of contents', 'function and variable index', 'environment variable index',
    'concept index', 'next:', 'previous:', 'up:', 'this is a guide to installation',
    'permission is granted to make and distribute verbatim copies',
)

ATS_HOST_PARTS = (
    'greenhouse.io', 'lever.co', 'ashbyhq.com', 'workdayjobs.com', 'myworkdayjobs.com',
    'smartrecruiters.com', 'workable.com', 'jobvite.com', 'icims.com', 'bamboohr.com',
)

JOB_PATH_PARTS = ('/jobs/', '/job/', '/careers/', '/career/', '/vacancy/', '/vacancies/', '/positions/')


def _norm(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '').replace('\xa0', ' ')).strip().lower()


def _contains_any(blob: str, items) -> list[str]:
    return [item for item in items if item in blob]


def classify_role_page(url: str, title: str, text: str, *, has_jobposting_schema: bool = False, is_pdf: bool = False) -> dict:
    """Return explainable role classification.

    `accepted=False` means the page should not enter the normal Opportunity list.  It
    may still be useful to Hidden Market if it describes relevant technical work.
    """
    title_n = _norm(title)
    body = _norm(text)
    sample = body[:50000]
    parts = urlsplit(url or '')
    host = (parts.netloc or '').lower()
    path = (parts.path or '').lower()

    score = 0
    positive = []
    negative = []

    if is_pdf:
        score -= 6
        negative.append('PDF result; job posts are uncommon in PDF form')

    if has_jobposting_schema:
        score += 12
        positive.append('JobPosting structured data')

    if any(x in host for x in ATS_HOST_PARTS):
        score += 8
        positive.append('recognized applicant-tracking site')
    if any(x in path for x in JOB_PATH_PARTS):
        score += 4
        positive.append('job/career URL')

    strong = _contains_any(sample, STRONG_ROLE_PHRASES)
    if strong:
        score += min(10, 5 + 2 * (len(strong) - 1))
        positive.extend(strong[:4])

    sections = _contains_any(sample, ROLE_SECTION_PHRASES)
    if sections:
        score += min(8, 2 * len(sections))
        positive.extend(sections[:4])

    # Role-shaped result titles help, but are deliberately weaker than application
    # language because articles can mention "engineer" without being vacancies.
    if any(re.search(rf'\b{re.escape(term)}\b', title_n) for term in ROLE_TITLE_TERMS):
        score += 3
        positive.append('role-shaped page title')

    # Typical job pages contain several employment phrases even if they omit a formal
    # JobPosting schema.
    employment_terms = _contains_any(sample, (
        'full-time', 'full time', 'part-time', 'part time', 'contract position',
        'employment', 'candidate', 'applicant', 'recruiter', 'hiring manager',
    ))
    if len(employment_terms) >= 2:
        score += 3
        positive.append('employment/application wording')

    title_noise = _contains_any(title_n, NON_ROLE_TITLE_PHRASES)
    if title_noise:
        score -= 9
        negative.extend(title_noise[:3])
    url_noise = [x for x in NON_ROLE_URL_PARTS if x in path]
    if url_noise:
        score -= 6
        negative.append('documentation/reference URL')
    doc_noise = _contains_any(sample, DOC_BODY_PHRASES)
    if len(doc_noise) >= 2:
        score -= 10
        negative.append('manual/documentation structure')

    # A long technical page with no application/hiring structure is not a role just
    # because a search query happened to match a skill phrase.
    has_actionable = bool(has_jobposting_schema or strong or sections or any(x in host for x in ATS_HOST_PARTS))
    if len(sample) > 3500 and not has_actionable:
        score -= 4
        negative.append('long page without role/application signals')

    # Require either strong evidence or a high aggregate score.  A title containing
    # "engineer" alone is never sufficient.
    accepted = bool(has_jobposting_schema or any(x in host for x in ATS_HOST_PARTS) or score >= (9 if is_pdf else 7))
    if title_noise and not (has_jobposting_schema or strong):
        accepted = False
    if len(doc_noise) >= 2 and not (has_jobposting_schema or strong):
        accepted = False

    if accepted:
        reason = 'Actionable role/engagement evidence found.'
    elif positive:
        reason = 'Some role-like terms were present, but there was not enough evidence of an actionable role.'
    else:
        reason = 'No actionable role/engagement evidence found; query-keyword overlap alone is insufficient.'

    return {
        'accepted': accepted,
        'score': max(-20, min(30, score)),
        'reason': reason,
        'positive_signals': list(dict.fromkeys(positive))[:8],
        'negative_signals': list(dict.fromkeys(negative))[:8],
    }

# High-noise media/search-result patterns that should never become Opportunities merely
# because a query term appears in a title, transcript or recommendation page.
HARD_NOISE_HOSTS = ('youtube.com', 'music.youtube.com', 'youtu.be')
HARD_NOISE_PHRASES = (
    'youtube music', 'official music video', 'official audio', 'playlist', 'watch on youtube',
    'full movie', 'episode ', 'trailer', 'lyrics', 'music video', 'subscribe to the channel',
)

_original_classify_role_page = classify_role_page

def classify_role_page(url: str, title: str, text: str, *, has_jobposting_schema: bool = False, is_pdf: bool = False) -> dict:
    parts=urlsplit(url or '')
    host=(parts.netloc or '').lower().removeprefix('www.')
    title_n=_norm(title); sample=_norm(text)[:12000]
    query=(parts.query or '').lower(); path=(parts.path or '').lower()
    if re.search(r'\bsearch\s+\d+\s+.+?jobs?\b',title_n) or ((('page=' in query) or ('sort=' in query)) and any(x in path for x in ('/jobs/','/careers/','/positions/'))):
        return {'accepted':False,'score':-20,'reason':'Aggregate job-list/search page; individual role URLs must be processed instead.','positive_signals':[],'negative_signals':['aggregate job listing']}
    if any(host == h or host.endswith('.'+h) for h in HARD_NOISE_HOSTS):
        return {'accepted':False,'score':-20,'reason':'Media/video source rejected as non-opportunity noise.','positive_signals':[],'negative_signals':['media/video source']}
    if any(p in title_n or p in sample[:2500] for p in HARD_NOISE_PHRASES):
        # A structured JobPosting payload is allowed to override generic wording, but
        # ordinary entertainment/media content is rejected deterministically.
        if not has_jobposting_schema:
            return {'accepted':False,'score':-20,'reason':'Entertainment/media content rejected as non-role noise.','positive_signals':[],'negative_signals':['entertainment/media content']}
    return _original_classify_role_page(url,title,text,has_jobposting_schema=has_jobposting_schema,is_pdf=is_pdf)

# v0.8.20: editorial/comparison/community pages can contain many technical role words
# but are not actionable opportunities. Reject them unless the page itself carries a
# strong hiring signal or JobPosting schema.
_v0820_classify_role_page = classify_role_page
_EDITORIAL_TITLE_PATTERNS = (
    r'\bcomparisons?\b', r'\bunbiased\s+hardware\b', r'\bproduct\s+reviews?\b',
    r'\bbenchmark(?:s|ing)?\b', r'\bsupport\s+forums?\b', r'\bcommunity\s+forums?\b',
    r'\bdiscussion\s+forums?\b', r'\bhow\s+to\b', r'\btutorial\b',
)
_EDITORIAL_BODY_MARKERS = (
    'compare products', 'hardware comparison', 'user reviews', 'support forum',
    'community forum', 'discussion thread', 'related articles', 'latest articles',
)

def classify_role_page(url: str, title: str, text: str, *, has_jobposting_schema: bool = False, is_pdf: bool = False) -> dict:
    title_n=_norm(title); sample=_norm(text)[:18000]
    strong=bool(_contains_any(sample,STRONG_ROLE_PHRASES))
    if not has_jobposting_schema and not strong:
        if any(re.search(p,title_n) for p in _EDITORIAL_TITLE_PATTERNS):
            return {'accepted':False,'score':-20,'reason':'Editorial/comparison/support page rejected as non-opportunity content.','positive_signals':[],'negative_signals':['editorial/comparison/support page']}
        if sum(1 for marker in _EDITORIAL_BODY_MARKERS if marker in sample)>=2:
            return {'accepted':False,'score':-20,'reason':'Community/editorial page rejected as non-opportunity content.','positive_signals':[],'negative_signals':['community/editorial content']}
    return _v0820_classify_role_page(url,title,text,has_jobposting_schema=has_jobposting_schema,is_pdf=is_pdf)

# v0.10.37: deterministic soft-404/closed-job handling. A HTTP 200 response does not
# make a role active when the visible page explicitly says applications are closed,
# the role is filled/expired, or the requested posting is no longer present.
_v01037_classify_role_page = classify_role_page

def classify_role_page(url: str, title: str, text: str, *, has_jobposting_schema: bool = False, is_pdf: bool = False) -> dict:
    from .content_quality import soft_missing_reason
    missing=soft_missing_reason(title,text)
    if missing:
        return {'accepted':False,'score':-20,
                'reason':'Soft 404 / inactive opportunity: '+missing+'.',
                'positive_signals':[],'negative_signals':['soft 404',missing]}
    return _v01037_classify_role_page(url,title,text,has_jobposting_schema=has_jobposting_schema,is_pdf=is_pdf)

# 0.10.94: source-integrity gate. These failures are non-overridable by semantic AI;
# they indicate that the input is a dataset/code/search dump rather than one vacancy.
_v01094_classify_role_page = classify_role_page
_DATA_FILE_SUFFIXES=('.json','.jsonl','.csv','.tsv','.xlsx','.xls','.parquet','.ndjson')
_SERIALIZED_MARKERS=(
    ':crawled', ':title', ':description', '"crawled":', '"description":',
    '"job_title":', '"jobs": [', 'serialized', 'dataset', 'rows": [',
)


def _hard_role_source_reject(url: str, title: str, text: str) -> str:
    parts=urlsplit(url or '')
    host=(parts.netloc or '').lower().removeprefix('www.')
    path=(parts.path or '').lower()
    title_raw=re.sub(r'\s+',' ',str(title or '')).strip()
    blob=(str(title or '')+'\n'+str(text or '')[:18000]).lower()
    marker_hits=sum(1 for marker in _SERIALIZED_MARKERS if marker in blob)
    if host=='gist.github.com' or host.endswith('.gist.github.com'):
        if marker_hits>=2 or any(x in blob for x in ('job dataset','scraped jobs','crawled true','{:crawled')):
            return 'GitHub Gist contains serialized/harvested job data rather than an individual vacancy.'
    if path.endswith(_DATA_FILE_SUFFIXES) and marker_hits>=1:
        return 'Structured data file/dataset rejected as a direct vacancy source.'
    if marker_hits>=3:
        return 'Serialized job-data/code dump rejected as a direct vacancy source.'
    if re.search(r'\{?\s*:?(?:crawled|title|description)\b',title_raw,re.I) and len(title_raw)>80:
        return 'Serialized field content was captured as the role title.'
    if len(title_raw)>220 and (title_raw.count('.')>=2 or ':' in title_raw):
        return 'Role title contains an implausibly large description/data fragment.'
    if any(x in path for x in ('/search','/results')) and ('jobs' in blob[:4000] or 'search results' in blob[:4000]):
        return 'Search-result/listing dump rejected; an individual role URL is required.'
    # Job-board search/SEO shells can masquerade as a single role when the requested
    # role appears in the page title. They are collections, not one employer vacancy.
    if re.search(r'(?i)\b[a-z0-9 +#/.&-]{2,120}\s+jobs?\s+in\s+[^|–—]{2,100}(?:\s*[|–—-]\s*(?:indeed|jobstreet|jobsdb|seek|glassdoor|linkedin))?\s*$',title_raw):
        return 'Job-board collection/search title rejected; an individual vacancy is required.'
    aggregate_markers=(
        'salary search:', 'see popular questions & answers about', 'view all ',
        'jobs in ', 'job return to search result', 'search jobs', 'job search results',
    )
    marker_hits=sum(1 for marker in aggregate_markers if marker in blob[:9000])
    if marker_hits>=3 and not has_concrete_vacancy_copy(blob):
        return 'Job-board collection/navigation content rejected; no concrete vacancy body was found.'
    shell_markers=('employers register for free','post a job','products & prices','customer service')
    shell_hits=sum(1 for marker in shell_markers if marker in blob[:8000])
    if shell_hits>=3 and not has_concrete_vacancy_copy(blob):
        return 'Job-board employer/navigation shell rejected as non-vacancy content.'
    if 'how many years\' experience do you have as a' in blob[:12000] and not has_concrete_vacancy_copy(blob):
        return 'Application-questionnaire shell rejected because the actual job description is missing.'
    return ''


def has_concrete_vacancy_copy(blob: str) -> bool:
    """Conservative body check used only to avoid false hard-rejects on real board JDs."""
    sample=str(blob or '').casefold()[:18000]
    role_sections=sum(1 for marker in (
        'responsibilities','requirements','qualifications','what you will do',"what you'll do",
        'about the role','about the job','your role','minimum qualifications','preferred qualifications',
    ) if marker in sample)
    hiring=sum(1 for marker in (
        'apply now','apply for this job','submit your application','we are hiring',"we're hiring",
        'we are looking for',"we're looking for",'we are seeking',"we're seeking",
    ) if marker in sample)
    return bool(role_sections>=2 or (role_sections>=1 and hiring>=1))


def classify_role_page(url: str, title: str, text: str, *, has_jobposting_schema: bool = False, is_pdf: bool = False) -> dict:
    hard_reason=_hard_role_source_reject(url,title,text)
    if hard_reason:
        return {'accepted':False,'hard_reject':True,'score':-30,'reason':hard_reason,
                'positive_signals':[],'negative_signals':['invalid opportunity source/structure']}
    result=_v01094_classify_role_page(url,title,text,has_jobposting_schema=has_jobposting_schema,is_pdf=is_pdf)
    if isinstance(result,dict):
        result.setdefault('hard_reject',False)
    return result
