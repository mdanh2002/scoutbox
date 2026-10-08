from django.db import migrations
import re


PLATFORM_NAMES={
    'linkedin','indeed','glassdoor','ziprecruiter','monster','simplyhired','jooble','careerjet','talent',
    'jobrapido','jobstreet','seek','jobsdb','dice','careerbuilder','wellfound','angellist','angel list',
    'builtin','built in','remoteok','remote ok','weworkremotely','we work remotely','remotive','himalayas',
    'jobicy','flexjobs','otta','sitepoint','work at a startup','y combinator','hacker news','startup jobs',
    'greenhouse','lever','ashby','ashbyhq','workable','smartrecruiters','bamboohr','recruitee','comeet',
    'jobvite','teamtailor','icims','workday','workday jobs','myworkdayjobs','successfactors','personio',
    'pinpointhq','jazzhr','hirebridge','applytojob','zohorecruit','freshteam','talentreef','taleo',
}


def _key(value):
    return re.sub(r'[^a-z0-9]+',' ',str(value or '').casefold()).strip()


def _platform(value):
    key=_key(value)
    return bool(key and key in PLATFORM_NAMES)


def _candidate_from_text(text):
    text=' '.join(str(text or '').split())
    if not text:
        return ''
    patterns=(
        r'\b([A-Z][A-Za-z0-9&.+\- ]{1,80}?)\s+(?:seeks|is seeking|is hiring|is looking for|is recruiting|needs|wants)\b',
        r'\b(?:role|position|job)\s+at\s+([A-Z][A-Za-z0-9&.+\- ]{1,80}?)(?=\s+(?:to|for|integrating|building|developing|designing|working|focused|focusing|with|seeks|is)\b|[,.]|$)',
    )
    for pattern in patterns:
        m=re.search(pattern,text,re.I)
        if not m:
            continue
        value=' '.join(m.group(1).split()).strip(' -–—,:;')[:220]
        if len(value)>=2 and not _platform(value):
            return value
    return ''


def _jsonld_company(facts):
    if not isinstance(facts,dict):
        return ''
    for key in ('description_html','raw_html','page_html'):
        raw=str(facts.get(key) or '')
        m=re.search(r'"hiringOrganization"\s*:\s*\{.{0,2000}?"name"\s*:\s*"([^"\\]{2,220})"',raw,re.I|re.S)
        if m:
            value=' '.join(m.group(1).replace('\\u0026','&').split()).strip()
            if value and not _platform(value):
                return value[:220]
    return ''


def repair_platform_identity(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')

    for row in Opportunity.objects.all().iterator(chunk_size=250):
        if not _platform(getattr(row,'company','')):
            continue
        facts=getattr(row,'extracted_facts',{}) or {}
        candidate=_jsonld_company(facts)
        if not candidate:
            for value in (getattr(row,'list_highlight',''),getattr(row,'raw_search_snippet',''),getattr(row,'description','')):
                candidate=_candidate_from_text(value)
                if candidate:
                    break
        row.company=candidate or ''
        # Platform-derived age/size/location data is not employer data. Clear it even
        # when the employer cannot yet be recovered; rediscovery/Re-evaluate can refill it.
        row.company_intel={}
        row.save(update_fields=['company','company_intel'])

    for row in CompanyLead.objects.all().iterator(chunk_size=250):
        if not _platform(getattr(row,'company','')):
            continue
        candidate=''
        for value in (getattr(row,'summary',''),getattr(row,'match_summary',''),getattr(row,'evidence','')):
            candidate=_candidate_from_text(value)
            if candidate:
                break
        row.company=candidate or ''
        row.company_intel={}
        row.save(update_fields=['company','company_intel'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0113_v01088_blacklist_domain_recovery')]
    operations=[migrations.RunPython(repair_platform_identity,noop_reverse)]
