import re
from urllib.parse import urlsplit
from django.db import migrations
from django.utils import timezone

FOREIGN=re.compile(r'[\u1100-\u11ff\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\u0400-\u052f\u0600-\u06ff\u0750-\u077f\u0e00-\u0e7f\u1780-\u17ff]+')
LATIN=re.compile(r'[A-Za-z]{2,}')
ROLE_WORD=re.compile(r'(?i)\b(engineer|developer|consultant|architect|writer|technical|firmware|software|linux|embedded|systems?|principal|specialist|manager|director|lead|scientist|researcher|designer|devops|security|platform|kernel|administrator|analyst|programmer)\b')
ADULT=[
    re.compile(r'\b(?:porn|pornographic|xxx|hardcore|explicit sex|sex video|adult video|adult content|adult entertainment|nude(?:s| photos?| videos?)?|camgirl|webcam sex)\b',re.I),
    re.compile(r'\b(?:escort service|escorts?|sexual services?|hookup sex|casual sex|live sex|sex chat|sticky service)\b',re.I),
    re.compile(r'\b(?:blowjob|handjob|anal sex|oral sex|gangbang|cumshot|masturbat(?:e|ion|ing)|MILF|slut|pussy|cock|dick)\b',re.I),
    re.compile(r'\b(?:married woman|woman gives|man(?:\'s)? cock)\b.*\b(?:sticky service|cock|sex|porn)\b',re.I),
]
PLATFORM_HOSTS=(
    'indeed.com','glassdoor.com','linkedin.com','ziprecruiter.com','simplyhired.com','monster.com',
    'jobsdb.com','jobsdb.co.th','jobsdb.com.hk','jobstreet.com','seek.com.au','seek.co.nz','wanted.co.kr',
    'weworkremotely.com','remoteok.com','remote.co','wellfound.com','angel.co','himalayas.app',
    'ycombinator.com','workatastartup.com','news.ycombinator.com','hackernews.com',
    'greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com',
    'bamboohr.com','recruitee.com','teamtailor.com','personio.de','jobvite.com','taleo.net','icims.com','breezy.hr',
    'facebook.com','reddit.com','x.com','twitter.com','youtube.com','github.com','gitlab.com',
)
PLATFORM_ALIASES={
    'indeed','glassdoor','linkedin','ziprecruiter','simplyhired','monster','jobsdb','jobstreet','seek','wanted',
    'we work remotely','weworkremotely','remote ok','remoteok','remote co','wellfound','angel list','angellist','himalayas',
    'y combinator','yc work at a startup','work at a startup','hacker news','hackernews',
    'greenhouse','lever','ashby','ashbyhq','workday','workday jobs','myworkdayjobs','smartrecruiters','workable',
    'bamboohr','recruitee','teamtailor','personio','jobvite','taleo','icims','breezy','facebook','reddit','twitter','youtube','github','gitlab'
}

def label_key(value):
    text=str(value or '').casefold()
    text=re.sub(r'\b(?:inc|llc|ltd|limited|corp|corporation|company|co|gmbh|plc|pty|group|holdings)\b',' ',text)
    return re.sub(r'[^a-z0-9]+',' ',text).strip()

def platform_label(value):
    key=label_key(value)
    if not key: return False
    aliases={label_key(x) for x in PLATFORM_ALIASES}
    compact=key.replace(' ','')
    if key in aliases or compact in {x.replace(' ','') for x in aliases}: return True
    suffix={'jobs','job','career','careers','work','startup','startups','who','is','hiring'}
    for alias in aliases:
        if alias and (key.startswith(alias+' ') or key.endswith(' '+alias) or (' '+alias+' ') in (' '+key+' ')):
            remainder=re.sub(r'(^| )'+re.escape(alias)+r'( |$)',' ',key).strip()
            if not remainder or set(remainder.split()).issubset(suffix): return True
    return bool(set(key.split()).issubset({x.replace(' ','') for x in aliases}|suffix))

def host(value):
    text=str(value or '').strip().lower()
    try:
        if '://' in text or '/' in text:
            text=(urlsplit(text).hostname or '').lower()
    except Exception:
        text=''
    return text.strip('.').removeprefix('www.')

def platform_host(value):
    h=host(value)
    if not h: return False
    labels={x for x in h.split('.') if x}
    brands={label_key(x).replace(' ','') for x in PLATFORM_ALIASES}
    return any(h==d or h.endswith('.'+d) for d in PLATFORM_HOSTS) or bool(labels.intersection(brands))

def clean_text(value):
    text=' '.join(str(value or '').replace('\xa0',' ').split()).strip(' -–—|·:;/,')
    if not text: return ''
    if FOREIGN.search(text) and not LATIN.search(text): return ''
    if FOREIGN.search(text):
        first=FOREIGN.search(text)
        prefix=text[:first.start()].strip(' -–—|·:;/,') if first else ''
        if prefix and LATIN.search(prefix) and not ROLE_WORD.search(text[first.end():]):
            text=prefix
        else:
            text=FOREIGN.sub(' ',text)
    text=re.sub(r'(?i)\b(?:new window|opens? in new|view who|applicants?|posted|promoted|save job|apply now|recruitment closed|job closed)\b.*$',' ',text)
    text=re.sub(r'(?i)\b(?:support|people|activity|less than|over|under)\s+\d+\b.*$',' ',text)
    text=re.sub(r'\s+(?:[-–—|·:/]\s*){2,}',' - ',text)
    text=re.sub(r'\s{2,}',' ',text).strip(' -–—|·:;/,')
    return '' if platform_label(text) else text

def fact_company(intel):
    if not isinstance(intel,dict): return ''
    for fact in intel.get('facts') or []:
        if isinstance(fact,dict) and str(fact.get('label') or '').strip().casefold()=='company':
            return str(fact.get('value') or '').strip()
    return ''

def source_urls(intel):
    out=[]
    if not isinstance(intel,dict): return out
    for row in intel.get('sources') or []:
        if isinstance(row,dict) and row.get('url'): out.append(str(row.get('url') or ''))
        elif isinstance(row,str): out.append(row)
    return out

def clean_intel(intel, row_company=''):
    intel=dict(intel or {}) if isinstance(intel,dict) else {}
    structured=dict(intel.get('structured') or {}) if isinstance(intel.get('structured'),dict) else {}
    candidates=[row_company,intel.get('company'),fact_company(intel)]
    platform_company=any(platform_label(x) for x in candidates if x)
    platform_domain=platform_host(structured.get('domain_age_domain'))
    urls=source_urls(intel)
    only_platform_sources=bool(urls) and all(platform_host(u) for u in urls)
    changed=False
    if platform_company:
        intel={'company':'','confidence':0,'facts':[],'sources':[],
               'errors':['Job board/platform is not a company identity; company information left unknown.'],
               'message':'Company information left unknown.','status':'complete','updated_at':timezone.now().isoformat(),'structured':{}}
        return intel, True
    if platform_domain or only_platform_sources:
        for key in ('domain_registered_at','domain_age_years','domain_age_label','domain_age_domain','founded_year','founded_by','age_range','size_range'):
            if key in structured:
                structured.pop(key,None); changed=True
        facts=[]
        for fact in intel.get('facts') or []:
            if not isinstance(fact,dict): continue
            label=str(fact.get('label') or '').casefold()
            if label in {'domain age','founded','founded by','size/structure','employee count/range'} or 'employee' in label or 'size' in label:
                changed=True; continue
            facts.append(fact)
        intel['facts']=facts[:12]; intel['structured']=structured
    return intel, changed

def normalise_result_counts(result):
    if not isinstance(result,dict): return result, False
    new=dict(result); changed=False
    if 'new_opportunities' in new:
        opp=int(new.get('new_opportunities') or 0)
    elif 'unique' in new:
        opp=int(new.get('unique') or 0)
    else:
        opp=int(new.get('opportunities_found') or 0)
    if new.get('opportunities_found')!=opp:
        new['opportunities_found']=opp; changed=True
    if new.get('new_opportunities')!=opp:
        new['new_opportunities']=opp; changed=True
    lead=int(new.get('new_leads') if new.get('new_leads') is not None else (new.get('leads_found') or 0))
    if new.get('leads_found')!=lead:
        new['leads_found']=lead; changed=True
    if new.get('new_leads')!=lead:
        new['new_leads']=lead; changed=True
    if isinstance(new.get('items'),list):
        for item in new['items']:
            if isinstance(item,dict):
                sub,sub_changed=normalise_result_counts(item)
                if sub_changed:
                    item.update(sub); changed=True
    return new, changed

def forwards(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    CampaignRun=apps.get_model('portal','CampaignRun')
    now=timezone.now()
    for row in Opportunity.objects.all().only('pk','title','company','company_intel').iterator(chunk_size=500):
        fields=[]
        title=clean_text(row.title) or 'Opportunity'
        if title!=row.title:
            row.title=title[:300]; fields.append('title')
        company=clean_text(row.company)
        if company!=row.company:
            row.company=company[:220]; fields.append('company')
        intel,changed=clean_intel(row.company_intel,row.company)
        if changed:
            row.company_intel=intel; fields.append('company_intel')
        if fields: row.save(update_fields=list(dict.fromkeys(fields)))
    for row in CompanyLead.objects.all().only('pk','company','summary','match_summary','evidence','target_url','source_url','company_intel','user_deleted','deleted_at').iterator(chunk_size=500):
        fields=[]
        blob=' '.join(str(x or '') for x in (row.company,row.summary,row.match_summary,row.evidence,row.target_url,row.source_url))[:30000]
        if not row.user_deleted and any(p.search(blob) for p in ADULT):
            row.user_deleted=True; row.deleted_at=now; fields+=['user_deleted','deleted_at']
        company=clean_text(row.company)
        if company!=row.company:
            row.company=company[:220]; fields.append('company')
        intel,changed=clean_intel(row.company_intel,row.company)
        if changed:
            row.company_intel=intel; fields.append('company_intel')
        if fields: row.save(update_fields=list(dict.fromkeys(fields)))
    for row in Contact.objects.all().only('pk','company','company_intel').iterator(chunk_size=500):
        fields=[]
        company=clean_text(row.company)
        if company!=row.company:
            row.company=company[:200]; fields.append('company')
        intel,changed=clean_intel(row.company_intel,row.company)
        if changed:
            row.company_intel=intel; fields.append('company_intel')
        if fields: row.save(update_fields=list(dict.fromkeys(fields)))
    for run in CampaignRun.objects.all().only('pk','result').iterator(chunk_size=500):
        fixed,changed=normalise_result_counts(run.result)
        if changed:
            run.result=fixed; run.save(update_fields=['result'])


def backwards(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies=[('portal','0094_v01043_regression_repairs')]
    operations=[migrations.RunPython(forwards,backwards)]
