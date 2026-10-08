import re
from urllib.parse import urlsplit, unquote
from django.db import migrations
from django.utils import timezone

FOREIGN=re.compile(r'[\u1100-\u11ff\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\u0400-\u052f\u0600-\u06ff\u0750-\u077f\u0e00-\u0e7f\u1780-\u17ff]+')
LATIN=re.compile(r'[A-Za-z]{2,}')
ROLE_WORD=re.compile(r'(?i)\b(engineer|developer|consultant|architect|writer|technical|firmware|software|linux|embedded|systems?|principal|specialist|manager|director|lead|scientist|researcher|designer|devops|security|platform|kernel|administrator|analyst|programmer)\b')
PLATFORM_ALIASES={
    'indeed','glassdoor','linkedin','ziprecruiter','simplyhired','monster','jobsdb','jobstreet','seek','wanted',
    'we work remotely','weworkremotely','remote ok','remoteok','remote co','wellfound','angel list','angellist','himalayas',
    'y combinator','yc work at a startup','work at a startup','hacker news','hackernews',
    'greenhouse','lever','ashby','ashbyhq','workday','workday jobs','myworkdayjobs','smartrecruiters','workable',
    'bamboohr','recruitee','teamtailor','personio','jobvite','taleo','icims','breezy','facebook','reddit','twitter','youtube','github','gitlab'
}
PLATFORM_HOSTS=(
    'indeed.com','glassdoor.com','linkedin.com','ziprecruiter.com','simplyhired.com','monster.com','jobsdb.com','jobsdb.co.th','jobsdb.com.hk',
    'jobstreet.com','seek.com.au','seek.co.nz','wanted.co.kr','weworkremotely.com','remoteok.com','remote.co','wellfound.com','angel.co',
    'himalayas.app','ycombinator.com','workatastartup.com','news.ycombinator.com','hackernews.com','greenhouse.io','lever.co','ashbyhq.com',
    'workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com','bamboohr.com','recruitee.com','teamtailor.com','personio.de',
    'jobvite.com','taleo.net','icims.com','breezy.hr','facebook.com','reddit.com','x.com','twitter.com','youtube.com','github.com','gitlab.com'
)
ROLE_STOP={'a','an','the','of','and','or','for','with','to','in','on','at','by','from'}
ACRONYMS={'ai','ml','qa','ui','ux','api','sdk','ios','gpu','cpu','fpga','rtos','bios','sre','devops','cicd','ci/cd','ea','mt5'}


def label_key(value):
    text=str(value or '').casefold()
    text=re.sub(r'\b(?:inc|llc|ltd|limited|corp|corporation|company|co|gmbh|plc|pty|group|holdings)\b',' ',text)
    return re.sub(r'[^a-z0-9]+',' ',text).strip()


def platform_label(value):
    key=label_key(value)
    if not key: return False
    compact=key.replace(' ','')
    aliases={label_key(x) for x in PLATFORM_ALIASES}
    if key in aliases or compact in {x.replace(' ','') for x in aliases}: return True
    suffix={'jobs','job','career','careers','work','startup','startups','who','is','hiring'}
    for alias in aliases:
        if alias and (key.startswith(alias+' ') or key.endswith(' '+alias) or (' '+alias+' ') in (' '+key+' ')):
            remainder=re.sub(r'(^| )'+re.escape(alias)+r'( |$)',' ',key).strip()
            if not remainder or set(remainder.split()).issubset(suffix): return True
    brand_tokens={x.replace(' ','') for x in aliases}
    return bool(set(key.split()) and set(key.split()).issubset(brand_tokens|suffix))


def platform_host(value):
    h=str(value or '').strip().lower().strip('.').removeprefix('www.')
    if '://' in h or '/' in h:
        try: h=(urlsplit(h).hostname or '').lower().strip('.').removeprefix('www.')
        except Exception: h=''
    if not h: return False
    brands={label_key(x).replace(' ','') for x in PLATFORM_ALIASES}
    return any(h==d or h.endswith('.'+d) for d in PLATFORM_HOSTS) or bool({x for x in h.split('.') if x}.intersection(brands))


def title_case_role(value):
    text=' '.join(str(value or '').split()).strip(' -–—|·:;/,.')
    text=re.sub(r'(?i)\s+(?:with|using|for|who|that|where|to)\s+.+$','',text).strip(' -–—|·:;/,.')
    out=[]
    for i,w in enumerate(text.split()):
        low=w.casefold()
        if low in ACRONYMS:
            out.append({'ios':'iOS','devops':'DevOps','ci/cd':'CI/CD'}.get(low,w.upper()))
        elif i>0 and low in ROLE_STOP:
            out.append(low)
        elif w.isupper() and len(w)<=5:
            out.append(w)
        else:
            out.append(re.sub(r'[A-Za-z]+',lambda m:m.group(0)[:1].upper()+m.group(0)[1:].lower(),w))
    return ' '.join(out).strip()


def clean_title(value, url=''):
    text=' '.join(str(value or '').replace('\xa0',' ').split()).strip(' -–—|·:;/,')
    if not text: return ''
    if FOREIGN.search(text) and not LATIN.search(text):
        text=''
    elif FOREIGN.search(text):
        first=FOREIGN.search(text)
        prefix=text[:first.start()].strip(' -–—|·:;/,') if first else ''
        if prefix and LATIN.search(prefix) and not ROLE_WORD.search(text[first.end():]): text=prefix
        else: text=FOREIGN.sub(' ',text)
    text=re.sub(r'(?i)^(?:discover\s*)?find\s+jobs\s*for\s+recruiters\s*log\s+in\s*sign\s+up\s*','',text).strip()
    if re.search(r'(?i)\s+at\s+',text):
        left=re.split(r'(?i)\s+at\s+',text,1)[0].strip(' -–—|·:;/,')
        if 4<=len(left)<=110 and ROLE_WORD.search(left): return title_case_role(left)
    patterns=(
        r'(?i)^\s*(?:we\s+(?:are\s+)?|our\s+team\s+is\s+)?(?:looking|searching)\s+for\s+(?:an?\s+)?(?P<role>(?:experienced\s+)?[A-Za-z][A-Za-z0-9+#./& -]{2,90}?)(?=\s+(?:to|who|with|for|that|using)\b|[.,;]|$)',
        r'(?i)^\s*[A-Z][A-Za-z0-9 .&-]{1,80}\s+(?:is\s+|are\s+)?(?:seeking|hiring|looking\s+for|recruiting)\s+(?:an?\s+)?(?P<role>[A-Za-z][A-Za-z0-9+#./& -]{2,90}?)(?=\s+(?:to|who|with|for|that|using)\b|[.,;]|$)',
        r'(?i)^\s*(?:seeking|hiring|wanted|required)\s+(?:an?\s+)?(?P<role>[A-Za-z][A-Za-z0-9+#./& -]{2,90}?)(?=\s+(?:to|who|with|for|that|using)\b|[.,;]|$)',
    )
    for pat in patterns:
        m=re.search(pat,text)
        if m and ROLE_WORD.search(m.group('role') or ''):
            return title_case_role(m.group('role'))
    text=re.sub(r'(?i)\b(?:new window|opens? in new|view who|applicants?|posted|promoted|save job|apply now|recruitment closed|job closed)\b.*$',' ',text)
    text=re.sub(r'(?i)\b(?:support|people|activity|less than|over|under)\s+\d+\b.*$',' ',text)
    text=re.sub(r'\s{2,}',' ',text).strip(' -–—|·:;/,')
    if (not text or len(text)>125 or not ROLE_WORD.search(text)) and url:
        try: slug=unquote(urlsplit(url).path.rstrip('/').rsplit('/',1)[-1])
        except Exception: slug=''
        slug=' '.join(x for x in re.split(r'[-_]+',slug) if x and not x.isdigit()).strip()
        if 4<=len(slug)<=110 and ROLE_WORD.search(slug): return title_case_role(slug)
    return '' if platform_label(text) else text


def fact_company(intel):
    if not isinstance(intel,dict): return ''
    for fact in intel.get('facts') or []:
        if isinstance(fact,dict) and str(fact.get('label') or '').strip().casefold()=='company':
            return str(fact.get('value') or '').strip()
    return ''


def source_urls(intel):
    if not isinstance(intel,dict): return []
    out=[]
    for row in intel.get('sources') or []:
        if isinstance(row,dict) and row.get('url'): out.append(str(row.get('url') or ''))
        elif isinstance(row,str): out.append(row)
    return out


def unknown_intel(message='Company could not be identified; company information left unknown.'):
    return {'company':'','confidence':0,'facts':[],'sources':[],'errors':[message],'message':message,'status':'complete','updated_at':timezone.now().isoformat(),'structured':{}}


def clean_intel(intel, row_company=''):
    intel=dict(intel or {}) if isinstance(intel,dict) else {}
    structured=dict(intel.get('structured') or {}) if isinstance(intel.get('structured'),dict) else {}
    candidates=[row_company,intel.get('company'),fact_company(intel)]
    if any(platform_label(x) for x in candidates if x):
        return unknown_intel('Job board/platform is not a company identity; company information left unknown.'), True
    real_company=any(str(x or '').strip() and not platform_label(x) for x in candidates)
    urls=source_urls(intel)
    platform_domain=platform_host(structured.get('domain_age_domain'))
    only_platform_sources=bool(urls) and all(platform_host(u) for u in urls)
    has_display=any(str(structured.get(k) or '').strip() for k in ('domain_registered_at','domain_age_years','domain_age_label','domain_age_domain','founded_year','founded_by','age_range','size_range'))
    has_display=has_display or any(isinstance(f,dict) and any(token in str(f.get('label') or '').casefold() for token in ('domain age','founded','employee','size')) for f in intel.get('facts') or [])
    if (not real_company and has_display) or platform_domain or only_platform_sources:
        return unknown_intel('Company identity is unknown or platform-derived; company information left unknown.'), True
    return intel, False


def forwards(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    prefix='CONTENT_NOT_JOB:'
    for row in Opportunity.objects.all().only('pk','title','company','target_url','company_intel','target_http_status','target_check_error').iterator(chunk_size=500):
        fields=[]
        title=clean_title(row.title,row.target_url) or 'Opportunity'
        if title!=row.title:
            row.title=title[:300]; fields.append('title')
        company='' if platform_label(row.company) else str(row.company or '')
        if company!=row.company:
            row.company=company[:220]; fields.append('company')
        intel,changed=clean_intel(row.company_intel,row.company)
        if changed:
            row.company_intel=intel; fields.append('company_intel')
        try:
            parsed=urlsplit(str(row.target_url or ''))
            wellfound=(parsed.hostname or '').lower().removeprefix('www.') in {'wellfound.com','angel.co'} and '/jobs/' in (parsed.path or '').lower()
        except Exception:
            wellfound=False
        if wellfound and row.target_http_status==200 and str(row.target_check_error or '').startswith(prefix):
            row.target_check_error=''; fields.append('target_check_error')
        if fields: row.save(update_fields=list(dict.fromkeys(fields)))
    for Model, max_company in ((CompanyLead,220),(Contact,200)):
        for row in Model.objects.all().only('pk','company','company_intel').iterator(chunk_size=500):
            fields=[]
            company='' if platform_label(row.company) else str(row.company or '')
            if company!=row.company:
                row.company=company[:max_company]; fields.append('company')
            intel,changed=clean_intel(row.company_intel,row.company)
            if changed:
                row.company_intel=intel; fields.append('company_intel')
            if fields: row.save(update_fields=list(dict.fromkeys(fields)))


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0095_v01044_release_repair')]
    operations=[migrations.RunPython(forwards,backwards)]
