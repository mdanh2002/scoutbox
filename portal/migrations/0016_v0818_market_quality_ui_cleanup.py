from django.db import migrations, models
import re
from urllib.parse import urlparse

WS=re.compile(r'\s+')
GENERIC=re.compile(r'(?i)\bgeneric[\s-]*full[\s-]*stack\b')
EXCLUDE=re.compile(r'(?<!\S)-(?:(?:"[^"]+")|(?:\'[^\']+\')|(?:[^\s]+))')
PUBLISHER_HOSTS={
    'xda-developers.com','hackaday.com','tomshardware.com','arstechnica.com','theverge.com',
    'slashdot.org','lobste.rs','reddit.com','medium.com','dev.to','stackoverflow.com','stackexchange.com',
}
DOC_HOSTS={'man7.org','manpages.ubuntu.com','linux.die.net','readthedocs.io','readthedocs.org','docs.python.org','developer.mozilla.org'}
COUNTRY_TLDS={'.sg':'Singapore','.au':'Australia','.uk':'United Kingdom','.de':'Germany','.fr':'France','.jp':'Japan','.ca':'Canada','.nz':'New Zealand','.ch':'Switzerland','.nl':'Netherlands','.se':'Sweden','.no':'Norway','.fi':'Finland','.in':'India','.br':'Brazil'}
COUNTRIES=('Singapore','Australia','United Kingdom','United States','Germany','France','Japan','Canada','New Zealand','Switzerland','Netherlands','Sweden','Norway','Finland','India','Brazil','Malaysia','Indonesia','Vietnam','Thailand','Philippines','China','Taiwan','Hong Kong','South Korea')


def host_of(value):
    try:return (urlparse(str(value or '')).netloc or '').lower().split('@')[-1].split(':')[0].removeprefix('www.')
    except Exception:return ''


def known_noise(row):
    urls=[getattr(row,x,'') for x in ('target_url','source_url','search_url')]
    for url in urls:
        host=host_of(url); path=(urlparse(str(url or '')).path or '').lower()
        if any(host==x or host.endswith('.'+x) for x in PUBLISHER_HOSTS|DOC_HOSTS):return True
        if host.startswith(('wiki.','docs.','documentation.','man.','manual.','help.','kb.')):return True
        if any(seg in path for seg in ('/wiki/','/docs/','/documentation/','/manual/','/man/','/man-pages/','/reference/','/api-reference/')):return True
    return False


def strip_company_prefix(text,company):
    out=WS.sub(' ',str(text or '')).strip().strip('"')
    if company:
        out=re.sub(r'(?i)^'+re.escape(str(company).strip())+r'\s+(?:is|are|works on|specialises in|specializes in|develops|builds|provides|offers)\s+','',out).strip()
    return out


def useful_summary(company,evidence):
    clean=WS.sub(' ',str(evidence or '')).strip()
    if not clean:return ''
    scored=[]
    boiler=(' cookie ',' privacy policy ',' sign in ',' log in ',' subscribe ',' all rights reserved ',' apply now ',' job opening ',' latest news ',' forum thread ')
    action=(' develops ',' builds ',' provides ',' offers ',' creates ',' maintains ',' designs ',' supports ',' produces ',' manufactures ',' specialises ',' specializes ',' focuses on ',' platform ',' product ',' service ',' project ',' software ',' hardware ',' firmware ',' engineering ',' research ')
    for sent in re.split(r'(?<=[.!?])\s+',clean[:12000]):
        sent=strip_company_prefix(sent,company); words=sent.split(); low=' '+sent.lower()+' '
        if not 10<=len(words)<=60:continue
        if any(x in low for x in boiler):continue
        score=sum(2 for x in action if x in low)
        if any(x in low for x in (' reverse engineering ',' embedded ',' emulation ',' virtualization ',' device driver ',' low-level ',' legacy ',' protocol ')):score+=1
        if score:scored.append((score,sent))
    scored.sort(key=lambda x:x[0],reverse=True)
    chosen=[]; total=0
    for _,sent in scored[:5]:
        n=len(sent.split())
        if chosen and total+n>58:continue
        chosen.append(sent.rstrip()); total+=n
        if total>=34 or len(chosen)>=2:break
    if not chosen:
        # Better to leave a summary pending than retain an unsupported keyword-only claim.
        return ''
    out=' '.join(chosen).strip(); words=out.split()
    if len(words)>62:out=' '.join(words[:62]).rstrip(' ,.;:')+'…'
    elif out and out[-1] not in '.!?':out+='.'
    return out[:900]


def infer_country(urls,text):
    blob=' '+WS.sub(' ',str(text or '')).lower()[:18000]+' '
    aliases={'united states of america':'United States','u.s.':'United States','usa':'United States','u.k.':'United Kingdom','uk':'United Kingdom'}
    for alias,name in aliases.items():
        if re.search(r'(?<![a-z])'+re.escape(alias)+r'(?![a-z])',blob):return name
    for name in COUNTRIES:
        if ' '+name.lower()+' ' in blob:return name
    for url in urls:
        host=host_of(url)
        if host.endswith('.edu'):return 'United States'
        for tld,name in COUNTRY_TLDS.items():
            if host.endswith(tld):return name
    return ''


def clean_queryish(value):
    text=EXCLUDE.sub(' ',str(value or '')); text=GENERIC.sub(' ',text); return WS.sub(' ',text).strip()


def clean_json(value):
    if isinstance(value,dict):return {k:clean_json(v) for k,v in value.items()}
    if isinstance(value,list):return [clean_json(v) for v in value]
    if isinstance(value,str):return clean_queryish(value)
    return value


def forwards(apps,schema_editor):
    Lead=apps.get_model('portal','CompanyLead')
    for row in Lead.objects.all().iterator():
        if known_noise(row):
            row.delete(); continue
        evidence=' '.join(x for x in (getattr(row,'evidence',''),getattr(row,'match_summary','')) if x)
        new=useful_summary(row.company,evidence)
        country=row.country or infer_country([row.target_url,row.source_url,row.search_url],evidence)
        changed=[]
        if new!=row.summary:row.summary=new;changed.append('summary')
        if country!=row.country:row.country=country;changed.append('country')
        if changed:row.save(update_fields=changed)

    # Re-scrub persistent search surfaces in case an old worker wrote legacy unary
    # exclusions after the previous migration but before this upgrade was installed.
    Campaign=apps.get_model('portal','Campaign')
    for row in Campaign.objects.all().iterator():
        changed=[]
        for field in ('role_families','technologies','extra_text','negative_constraints'):
            old=getattr(row,field,''); new=clean_queryish(old)
            if new!=old:setattr(row,field,new);changed.append(field)
        if changed:row.save(update_fields=changed)
    Template=apps.get_model('portal','CampaignTemplate')
    for row in Template.objects.all().iterator():
        changed=[]
        for field in ('role_families','technologies'):
            old=getattr(row,field,None)
            if isinstance(old,list):new=[x for x in (clean_queryish(v) for v in old) if x]
            else:new=old
            if new!=old:setattr(row,field,new);changed.append(field)
        for field in ('extra_text','negative_constraints'):
            old=getattr(row,field,'');new=clean_queryish(old)
            if new!=old:setattr(row,field,new);changed.append(field)
        if changed:row.save(update_fields=changed)

    # Keep user-facing terminology consistent after upgrades.  Internal kind='cv' is
    # deliberately retained for backwards compatibility with stored files.
    Campaign.objects.filter(name='CV-first Automatic Discovery').update(name='Resume-first Automatic Discovery')
    Campaign.objects.filter(template='Automatic CV-first').update(template='Automatic Resume-first')
    Template.objects.filter(name='CV-first Automatic Discovery').update(name='Resume-first Automatic Discovery')
    Template.objects.filter(name='Automatic CV-first').update(name='Automatic Resume-first')

    for model_name,fields in [('CampaignRun',('criteria','query_plan','result')),('BackgroundJob',('result',)),('UsageMetric',('metadata',)),('Profile',('scope_json',)),('DiagnosticRun',('criteria','result'))]:
        Model=apps.get_model('portal',model_name)
        for row in Model.objects.all().iterator():
            changed=[]
            for field in fields:
                old=getattr(row,field,None)
                if old:
                    new=clean_json(old)
                    if new!=old:setattr(row,field,new);changed.append(field)
            if changed:row.save(update_fields=changed)

    Performance=apps.get_model('portal','PerformanceRun')
    for row in Performance.objects.all().iterator():
        changed=[]
        new_text=clean_queryish(row.input_text)
        if new_text!=row.input_text:row.input_text=new_text;changed.append('input_text')
        new_meta=clean_json(row.metadata)
        if new_meta!=row.metadata:row.metadata=new_meta;changed.append('metadata')
        if changed:row.save(update_fields=changed)

    SavedFilter=apps.get_model('portal','SavedFilter')
    for row in SavedFilter.objects.all().iterator():
        new=clean_queryish(row.query_string)
        if new!=row.query_string:
            row.query_string=new; row.save(update_fields=['query_string'])


class Migration(migrations.Migration):
    dependencies=[('portal','0015_v0817_summary_query_cleanup')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop), migrations.AlterField(model_name='documentasset',name='kind',field=models.CharField(max_length=20,choices=[('cv','Resume'),('cover','Cover letter')]))]
