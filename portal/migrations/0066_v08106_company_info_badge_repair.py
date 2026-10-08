import re
from urllib.parse import urlsplit
from django.db import migrations

PLATFORMS={
    'linkedin.com','indeed.com','glassdoor.com','ziprecruiter.com','simplyhired.com','monster.com',
    'greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com',
    'jobstreet.com','jobsdb.com','wearedevelopers.com',
}
FREE={'gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com','icloud.com','proton.me','protonmail.com','aol.com'}
TWO={'co.uk','org.uk','com.au','net.au','co.nz','com.sg','com.my','co.jp','co.in','com.br','com.mx','co.za'}


def _host(url):
    try:
        return (urlsplit(str(url or '')).hostname or '').lower().removeprefix('www.')
    except Exception:
        return ''


def _reg(host):
    labels=[x for x in str(host or '').lower().strip('.').split('.') if x]
    if len(labels)<=2:
        return '.'.join(labels)
    return '.'.join(labels[-3:]) if '.'.join(labels[-2:]) in TWO else '.'.join(labels[-2:])


def _bad_domain(domain):
    return not domain or domain in FREE or any(domain==p or domain.endswith('.'+p) for p in PLATFORMS)


def _domain(row):
    email=str(getattr(row,'contact_email',None) or getattr(row,'email','') or '').strip().lower()
    if '@' in email:
        d=_reg(email.rsplit('@',1)[1])
        if not _bad_domain(d):
            return d
    intel=getattr(row,'company_intel',{}) or {}
    if isinstance(intel,dict):
        structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
        d=_reg(str(structured.get('domain_age_domain') or ''))
        if not _bad_domain(d):
            return d
        for src in intel.get('sources') or []:
            url=src.get('url') if isinstance(src,dict) else src
            d=_reg(_host(url))
            if not _bad_domain(d):
                return d
    for field in ('target_url','url','source_url'):
        d=_reg(_host(getattr(row,field,'')))
        if not _bad_domain(d):
            return d
    return ''


def _key(value):
    return re.sub(r'[^a-z0-9]+','',str(value or '').casefold())


def _normalise_size(value):
    text=' '.join(str(value or '').split())
    m=re.search(r'(?<!\d)(\d{1,6})\s*(?:[–—-]|to)\s*(\d{1,6})(?!\d)',text,re.I)
    if m:
        a,b=int(m.group(1)),int(m.group(2))
        if 0<a<=b<=500000:
            return f'{a:,}–{b:,}'
    m=re.search(r'(?<!\d)(\d{1,6})\s*(\+)?\s*(?:employees?|people|staff)',text,re.I)
    if m:
        return f'{int(m.group(1)):,}'+('+' if m.group(2) else '')
    return ''


def _normalise(intel):
    if not isinstance(intel,dict):
        return {},False
    out=dict(intel)
    structured=dict(out.get('structured') or {}) if isinstance(out.get('structured'),dict) else {}
    changed=not isinstance(out.get('structured'),dict)
    founded=str(structured.get('founded_year') or '').strip()
    size=str(structured.get('size_range') or '').strip()
    domain_age=str(structured.get('domain_age_label') or '').strip()
    for fact in out.get('facts') or []:
        if not isinstance(fact,dict):
            continue
        label=str(fact.get('label') or '').casefold()
        value=str(fact.get('value') or '').strip()
        if not founded and ('founded' in label or 'established' in label):
            m=re.search(r'\b(18|19|20)\d{2}\b',value)
            if m:
                founded=m.group(0); structured['founded_year']=int(founded); changed=True
        if not size and ('size' in label or 'employee' in label):
            parsed=_normalise_size(value)
            if parsed:
                size=parsed; structured['size_range']=parsed; changed=True
        if not domain_age and label=='domain age':
            m=re.search(r'(?<!\d)(\d{1,3})\s*(?:yrs?|years?)\b',value,re.I)
            if m:
                n=int(m.group(1)); domain_age=f'{n} yr' if n==1 else f'{n} yrs'; structured['domain_age_label']=domain_age; changed=True
    has_display=bool(founded or structured.get('age_range') or domain_age or size)
    if not has_display and out.get('facts') and str(out.get('status') or '').casefold()=='complete':
        if not structured.get('domain_age_refresh_needed'):
            structured['domain_age_refresh_needed']=True; changed=True
    elif has_display and structured.pop('domain_age_refresh_needed',None) is not None:
        changed=True
    out['structured']=structured
    return out,changed


def _score(intel):
    intel,_=_normalise(intel)
    if not intel:
        return 0
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    score=0
    score += 80 if structured.get('founded_year') or structured.get('age_range') or structured.get('domain_age_label') else 0
    score += 80 if structured.get('size_range') else 0
    score += min(50,len([x for x in (intel.get('facts') or []) if isinstance(x,dict)])*5)
    score += min(20,len(intel.get('sources') or [])*2)
    try:
        score += int(intel.get('confidence') or 0)//4
    except Exception:
        pass
    return score


def repair(apps,schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    Lead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    Cache=apps.get_model('portal','CompanyResearchCache')

    best_company={}; best_domain={}
    def consider(company,domain,intel):
        normalised,_=_normalise(intel)
        if not normalised:
            return
        score=_score(normalised); ck=_key(company); d=_reg(domain)
        if ck and (ck not in best_company or score>best_company[ck][0]):
            best_company[ck]=(score,normalised)
        if d and not _bad_domain(d) and (d not in best_domain or score>best_domain[d][0]):
            best_domain[d]=(score,normalised)

    for Model in (Opportunity,Lead,Contact):
        for row in Model.objects.all().iterator(chunk_size=300):
            consider(getattr(row,'company',''),_domain(row),getattr(row,'company_intel',{}) or {})
    for cache in Cache.objects.all().iterator(chunk_size=300):
        consider(cache.company,cache.domain,cache.data if isinstance(cache.data,dict) else {})

    for Model in (Opportunity,Lead,Contact):
        batch=[]
        for row in Model.objects.all().iterator(chunk_size=300):
            current,changed=_normalise(getattr(row,'company_intel',{}) or {})
            candidates=[]; ck=_key(getattr(row,'company','')); d=_domain(row)
            if ck and ck in best_company:
                candidates.append(best_company[ck])
            if d and d in best_domain:
                candidates.append(best_domain[d])
            if candidates:
                candidate=max(candidates,key=lambda x:x[0])[1]
                if _score(candidate)>_score(current):
                    current=dict(candidate); changed=True
            # Mark remaining complete-but-profile-only records for a fresh domain/company
            # research pass. The runtime backfill resolves this without doing network work
            # inside the migration itself.
            current,normalised_changed=_normalise(current)
            changed=changed or normalised_changed
            if changed:
                row.company_intel=current
                batch.append(row)
                if len(batch)>=300:
                    Model.objects.bulk_update(batch,['company_intel'],batch_size=300); batch=[]
        if batch:
            Model.objects.bulk_update(batch,['company_intel'],batch_size=300)


class Migration(migrations.Migration):
    dependencies=[('portal','0065_v08105_salary_company_repair')]
    operations=[migrations.RunPython(repair,migrations.RunPython.noop)]
