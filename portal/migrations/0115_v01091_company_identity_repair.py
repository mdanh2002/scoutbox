from django.db import migrations
import re

PLATFORMS={'linkedin','indeed','glassdoor','ziprecruiter','monster','simplyhired','jooble','careerjet','talent','jobrapido','jobstreet','seek','jobsdb','dice','careerbuilder','wellfound','angellist','angel list','builtin','built in','working nomads','workingnomads','remoteok','remote ok','weworkremotely','we work remotely','remotive','himalayas','jobicy','flexjobs','otta','sitepoint','work at a startup','y combinator','hacker news','startup jobs','greenhouse','lever','ashby','ashbyhq','workable','smartrecruiters','bamboohr','recruitee','comeet','jobvite','teamtailor','icims','workday','workday jobs','myworkdayjobs','successfactors','personio'}
GENERIC={'team','catalog','security','infrastructure','platform','software','engineering','product','systems','automation','quality','assurance','backup','patching','cloud','mobile','backend','frontend','research','development','operations','business','solutions','department','division','unit'}
BAD_START={'and','or','with','for','from','to','in','of','by','as','using','including','across','focused','focuses','seeking','looking','requires','required','responsibilities','experience'}

def key(v): return re.sub(r'[^a-z0-9]+',' ',str(v or '').casefold()).strip()
def bad(v):
    k=key(v); words=k.split()
    if not words: return True
    if k in PLATFORMS or words[0] in BAD_START: return True
    if len(words)<=5 and set(words).issubset(GENERIC): return True
    if words[-1] in {'team','department','division','unit'} and len(words)<=6: return True
    return False

def candidate(text):
    t=' '.join(str(text or '').split())
    patterns=(
      r'\b([A-Z][A-Za-z0-9&+.’\'()\- ]{1,80}?)\s+(?:seeks|is seeking|is hiring|is looking for|looks for|hiring)\b',
      r'\b(?:engineer|developer|writer|manager|specialist|researcher|architect|consultant|analyst|designer|administrator|scientist)[^.]{0,110}?\s+at\s+([A-Z][A-Za-z0-9&+.’\'()\- ]{1,70}?)(?=[.,;]|\s+(?:build|develop|design|work|join|help|create)\b)',
      r'\b(?:role|position|job)\s+at\s+([A-Z][A-Za-z0-9&+.’\'()\- ]{1,80}?)(?=[,.]|$)',
    )
    for p in patterns:
        m=re.search(p,t,re.I)
        if m:
            v=' '.join(m.group(1).split()).strip(' -–—,:;')[:220]
            if not bad(v): return v
    return ''

def repair(apps,schema_editor):
    Opportunity=apps.get_model('portal','Opportunity'); CompanyLead=apps.get_model('portal','CompanyLead')
    for row in Opportunity.objects.all().iterator(chunk_size=250):
        if not bad(row.company): continue
        found=''
        for txt in (row.list_highlight,row.raw_search_snippet,row.description):
            found=candidate(txt)
            if found: break
        row.company=found or ''
        row.company_intel={}
        row.save(update_fields=['company','company_intel'])
    for row in CompanyLead.objects.all().iterator(chunk_size=250):
        if not bad(row.company): continue
        found=''
        for txt in (row.summary,row.match_summary,row.evidence):
            found=candidate(txt)
            if found: break
        row.company=found or ''
        row.company_intel={}
        row.save(update_fields=['company','company_intel'])

def noop(apps,schema_editor): pass

class Migration(migrations.Migration):
    dependencies=[('portal','0114_v01090_platform_identity_cleanup')]
    operations=[migrations.RunPython(repair,noop)]
