"""Shared job-board / ATS / discovery-platform classification.

Keep this module deliberately dependency-light.  Employer extraction, company research,
blacklist review, discovery and manual re-evaluation all use the same registry so a
listing host such as Built In can never silently become the hiring company.
"""
import re
from urllib.parse import urlsplit

TWO_PART_SUFFIXES={
    'co.uk','org.uk','ac.uk','gov.uk','com.au','net.au','org.au','co.nz','com.sg','com.my',
    'com.hk','com.br','com.mx','com.tr','co.jp','com.cn','com.tw','co.kr','co.in','co.za',
}

JOB_BOARD_DOMAINS={
    'linkedin.com','indeed.com','glassdoor.com','ziprecruiter.com','monster.com','simplyhired.com',
    'jooble.org','careerjet.com','talent.com','jobrapido.com','jobstreet.com','seek.com.au','seek.co.nz',
    'jobsdb.com','jobsdb.co.th','jobsdb.com.hk','dice.com','careerbuilder.com','wellfound.com','angel.co',
    'builtin.com','workopolis.com','gulftalent.com','workingnomads.com','workingnomads.co','remoteok.com','weworkremotely.com','remote.co','remotive.com','himalayas.app','jobicy.com',
    'flexjobs.com','otta.com','cord.co','sitepoint.com','workatastartup.com','ycstartupjobs.com','startup.jobs',
    'startupjobs.com','levels.fyi','theorg.com','wanted.co.kr','ycombinator.com','news.ycombinator.com',
    'hackernews.com','findjob24h.com','freelancer.com','upwork.com','fiverr.com','peopleperhour.com','guru.com',
}

ATS_DOMAINS={
    'workable.com','greenhouse.io','lever.co','ashbyhq.com','smartrecruiters.com','bamboohr.com','recruitee.com',
    'comeet.com','jobvite.com','teamtailor.com','icims.com','myworkdayjobs.com','workdayjobs.com','successfactors.com',
    'personio.com','personio.de','pinpointhq.com','trakstar.com','jazzhr.com','paylocity.com','ultipro.com','ultipro.ca',
    'oraclecloud.com','hirebridge.com','applytojob.com','catsone.com','breezy.hr','rippling-ats.com','jobsoid.com',
    'zohorecruit.com','join.com','freshteam.com','talentreef.com','taleo.net',
}

DISCOVERY_PLATFORM_DOMAINS={
    'facebook.com','reddit.com','x.com','twitter.com','youtube.com','github.com','gitlab.com','bitbucket.org',
    'stackoverflow.com','stackexchange.com','medium.com','substack.com','dev.to','hashnode.com',
}

JOB_PLATFORM_DOMAINS=JOB_BOARD_DOMAINS | ATS_DOMAINS | DISCOVERY_PLATFORM_DOMAINS

PLATFORM_NAME_ALIASES={
    'linkedin','indeed','glassdoor','ziprecruiter','simplyhired','monster','jooble','careerjet','talent','jobrapido',
    'jobstreet','seek','jobsdb','workopolis','gulftalent','dice','careerbuilder','wellfound','angel list','angellist','built in','builtin','working nomads','workingnomads',
    'remote ok','remoteok','we work remotely','weworkremotely','remote co','remotive','himalayas','jobicy','flexjobs',
    'otta','cord','sitepoint','work at a startup','yc work at a startup','y combinator','hacker news','hackernews',
    'startup jobs','startupjobs','levels fyi','the org','wanted','greenhouse','lever','ashby','ashbyhq','workable',
    'smartrecruiters','bamboohr','recruitee','comeet','jobvite','teamtailor','icims','workday','workday jobs',
    'myworkdayjobs','successfactors','personio','pinpointhq','jazzhr','paylocity','ultipro','oraclecloud','hirebridge',
    'applytojob','catsone','breezy','rippling ats','jobsoid','zohorecruit','freshteam','talentreef','taleo',
    'facebook','reddit','twitter','x','youtube','github','gitlab','bitbucket','stackoverflow','stackexchange','medium',
    'substack','devto','hashnode','freelancer','upwork','fiverr','peopleperhour','guru',
}

LOOSE_PLATFORM_SIGNALS={
    'linkedin','indeed','glassdoor','ziprecruiter','builtin','workingnomads','himalayas','remoteok','weworkremotely','wellfound',
    'sitepoint','workopolis','gulftalent','greenhouse','lever','ashby','workable','smartrecruiters','recruitee','bamboohr','jobvite','teamtailor',
    'icims','myworkdayjobs','workdayjobs','successfactors','personio','pinpointhq','jazzhr','hirebridge','applytojob',
    'zohorecruit','freshteam','talentreef','jobstreet','jobsdb','careerbuilder','simplyhired','monster','remotive',
}


def host_from(value):
    raw=str(value or '').strip().lower()
    if not raw:
        return ''
    try:
        if '://' in raw:
            raw=urlsplit(raw).netloc
    except Exception:
        pass
    return raw.split('@')[-1].split(':',1)[0].strip('.').removeprefix('www.')


def registrable_domain(value):
    host=host_from(value)
    labels=[x for x in host.split('.') if x]
    if len(labels)<=2:
        return host
    tail='.'.join(labels[-2:])
    return '.'.join(labels[-3:]) if tail in TWO_PART_SUFFIXES else tail


def _matches_domain(host, domains):
    return any(host==d or host.endswith('.'+d) or registrable_domain(host)==registrable_domain(d) for d in domains)


def is_job_board_host(value):
    host=host_from(value)
    if not host:
        return False
    if _matches_domain(host,JOB_BOARD_DOMAINS):
        return True
    compact=re.sub(r'[^a-z0-9]+','',host)
    return any(signal in compact for signal in LOOSE_PLATFORM_SIGNALS if signal not in {'greenhouse','lever','ashby','workable','recruitee','bamboohr','jobvite','teamtailor','icims','workdayjobs','myworkdayjobs'})


def is_ats_host(value):
    host=host_from(value)
    if not host:
        return False
    if _matches_domain(host,ATS_DOMAINS):
        return True
    compact=re.sub(r'[^a-z0-9]+','',host)
    ats_signals={'greenhouse','lever','ashby','workable','smartrecruiters','recruitee','bamboohr','jobvite','teamtailor','icims','myworkdayjobs','workdayjobs','successfactors','personio','pinpointhq','jazzhr','hirebridge','applytojob','zohorecruit','freshteam','talentreef'}
    return any(signal in compact for signal in ats_signals)


def is_job_platform_host(value):
    host=host_from(value)
    if not host:
        return False
    if _matches_domain(host,JOB_PLATFORM_DOMAINS):
        return True
    compact=re.sub(r'[^a-z0-9]+','',host)
    return any(signal in compact for signal in LOOSE_PLATFORM_SIGNALS)


def is_direct_role_host_allowed(value):
    """ATS/company hosts can be exact role pages; public aggregators cannot."""
    return bool(host_from(value)) and not is_job_board_host(value)


def company_name_key(value):
    text=str(value or '').casefold()
    text=re.sub(r'\b(?:inc|incorporated|llc|ltd|limited|corp|corporation|company|co|gmbh|plc|pty|pte|group|holdings)\b',' ',text)
    return re.sub(r'[^a-z0-9]+',' ',text).strip()


def is_platform_company_name(value):
    key=company_name_key(value)
    if not key:
        return False
    compact=key.replace(' ','')
    aliases={company_name_key(x) for x in PLATFORM_NAME_ALIASES}
    compact_aliases={x.replace(' ','') for x in aliases}
    if key in aliases or compact in compact_aliases:
        return True
    suffix_words={'jobs','job','careers','career','work','startup','startups','who','is','hiring','vacancies','opportunities'}
    for alias in aliases:
        if alias and (key.startswith(alias+' ') or key.endswith(' '+alias) or (' '+alias+' ') in (' '+key+' ')):
            remainder=re.sub(r'(^| )'+re.escape(alias)+r'( |$)',' ',key).strip()
            if not remainder or set(remainder.split()).issubset(suffix_words):
                return True
    tokens={x for x in key.split() if x}
    alias_tokens={x for alias in aliases for x in alias.split()}
    return bool(tokens and tokens.issubset(alias_tokens | suffix_words))


_IMPLAUSIBLE_COMPANY_STARTS={
    'and','or','with','for','from','to','in','of','by','as','using','including','across','focused','focuses',
    'seeking','looking','requires','required','responsibilities','responsibility','experience','scalability',
    'our','your','their','this','that','these','those','what','who','we','allows','allowing','helps','helping','provides','provide','offers','offering','through','while','where',
}
_GENERIC_ORG_TOKENS={
    'team','catalog','security','infrastructure','platform','software','engineering','engineer','product','products',
    'systems','system','automation','quality','assurance','backup','patching','cloud','mobile','backend','frontend',
    'research','development','operations','business','solutions','solution','department','division','group','unit',
}
_FRAGMENT_SIGNALS={
    'with','using','building','developing','designing','scalability','experience','responsibilities','requirements',
    'required','across','including','supporting','focusing','focused','partnering','improving','delivering','providing',
    'allows','allowing','helps','helping','enables','enabling','offers','offering','recommend','recommends','updated','verified','integrates','integrating',
}
_JOB_DESCRIPTION_HEADING_COMPANIES={
    'what we','what we are','what we do','what we offer','what we provide','what we believe',
    "what we're","what we're looking for",'what you','what you will do',"what you'll do",
    'who we are','who we','who you are','we are','we have','about us','about the company',
    'the role','the company','the position','your role','our team','our company',
}

_JOB_BOARD_UI_COMPANY_MARKERS=(
    'employers register', 'register for free', 'post a job', 'products & prices',
    'products and prices', 'customer service', 'job search', 'search jobs',
)


def company_from_ats_url(url):
    """Return a conservative employer label encoded by a first-party ATS board URL.

    The board identifier is stronger identity evidence than free-form JD prose.  This is
    intentionally limited to ATS families whose public URL path directly names the hiring
    organization/board; generic job-board hosts are never interpreted as employers here.
    """
    try:
        p=urlsplit(str(url or '').strip())
        host=(p.hostname or '').lower()
        seg=[x for x in p.path.split('/') if x]
    except Exception:
        return ''
    token=''
    if 'greenhouse.io' in host and seg:
        token=seg[0]
    elif (host in {'jobs.lever.co','jobs.eu.lever.co'} or host.endswith('.jobs.lever.co')) and seg:
        token=seg[0]
    elif (host=='jobs.ashbyhq.com' or host.endswith('.jobs.ashbyhq.com')) and seg:
        token=seg[0]
    elif 'smartrecruiters.com' in host and seg:
        token=seg[0]
    if not token or not re.fullmatch(r'[A-Za-z0-9._-]{2,120}',token):
        return ''
    text=re.sub(r'[_-]+',' ',token).strip()
    # Preserve already mixed-case board labels; title-case machine slugs only.
    if text.islower() or text.isupper():
        text=text.title()
    return text[:160] if is_plausible_company_name(text) else ''


def is_plausible_company_name(value):
    """Conservative employer-name sanity check.

    A blank is preferable to treating a job-board label, department name or sentence
    fragment as the employer; stronger page evidence can fill the value later.
    """
    raw=re.sub(r'\s+',' ',str(value or '')).strip(' \t\r\n-–—|:;,')
    if not raw or len(raw)<2 or len(raw)>160 or is_platform_company_name(raw):
        return False
    key=company_name_key(raw)
    words=[w for w in key.split() if w]
    if not words:
        return False
    if words[0] in _IMPLAUSIBLE_COMPANY_STARTS:
        return False
    low=raw.casefold()
    if low in _JOB_DESCRIPTION_HEADING_COMPANIES or any(low.startswith(x+' ') for x in _JOB_DESCRIPTION_HEADING_COMPANIES):
        return False
    if re.search(r"(?i)^(?:what|who|why|how)\s+(?:we|you|our)\b", raw):
        return False
    if re.search(r"(?i)^(?:we|you|our|the)\s+(?:are|have|offer|believe|provide|build|look|looking|seek|seeking)\b", raw):
        return False
    if re.search(r"[.!?]\s+(?:we|you|our|the)\s+(?:are|have|offer|provide|build|seek|look)\b", raw, re.I):
        return False
    # Short department/team labels such as "Catalog Team" or "Infrastructure Security"
    # are not company identities.
    if len(words)<=5 and set(words).issubset(_GENERIC_ORG_TOKENS):
        return False
    if words[-1] in {'team','department','division','unit'} and len(words)<=6:
        return False
    # Long prose fragments are common when a local model slices the role summary at the
    # wrong delimiter.  Reject them rather than poisoning company intelligence.
    if len(words)>=5 and any(w in _FRAGMENT_SIGNALS for w in words):
        return False
    ui_hits=sum(1 for marker in _JOB_BOARD_UI_COMPANY_MARKERS if marker in low)
    if ui_hits>=2 or low in {'customer service','employer','employers','job search','search jobs','post a job'}:
        return False
    if any(marker in low for marker in ('about the role','job description','responsibilities include','we are seeking','we are looking for','our technology','our platform','our product','this role','this position')) and len(words)>=3:
        return False
    corporate_suffixes={'inc','incorporated','llc','ltd','limited','corp','corporation','company','co','gmbh','plc','pty','group','holdings','technologies','technology','systems','labs','laboratories','studio','studios','university','institute','foundation'}
    has_suffix=bool(set(words) & corporate_suffixes)
    if len(words)>=4 and not has_suffix and any(w in _FRAGMENT_SIGNALS for w in words):
        return False
    if len(words)>=6 and not has_suffix:
        return False
    if raw.count('.')>=2 and len(words)>=6:
        return False
    if raw[:1].islower() and len(words)>=3:
        return False
    return True
