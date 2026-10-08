import re
from urllib.parse import urlsplit
from django.db import migrations

NOISE=(
    r'\bsign\s+in\b.{0,120}\b(?:salary|pay)\b',
    r'\badd\s+(?:your\s+)?salary\b',
    r'\bcompetitive\s+(?:salary|compensation|pay)\b',
    r'\bperformance[- ]based\s+bonus\b',
)
PLATFORMS={'linkedin.com','indeed.com','glassdoor.com','ziprecruiter.com','simplyhired.com','monster.com','greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com','jobstreet.com','jobsdb.com','wearedevelopers.com'}
TWO={'co.uk','org.uk','com.au','net.au','co.nz','com.sg','com.my','co.jp','co.in','com.br','com.mx','co.za'}
FREE={'gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com','icloud.com','proton.me','protonmail.com','aol.com'}

def _host(url):
    try: return (urlsplit(str(url or '')).hostname or '').lower().removeprefix('www.')
    except Exception: return ''

def _reg(host):
    labels=[x for x in str(host or '').lower().strip('.').split('.') if x]
    if len(labels)<=2: return '.'.join(labels)
    return '.'.join(labels[-3:]) if '.'.join(labels[-2:]) in TWO else '.'.join(labels[-2:])

def _bad_domain(d): return not d or d in FREE or any(d==p or d.endswith('.'+p) for p in PLATFORMS)
def _key(v): return re.sub(r'[^a-z0-9]+','',str(v or '').casefold())

def _domain(row):
    email=str(getattr(row,'contact_email',None) or getattr(row,'email','') or '').strip().lower()
    if '@' in email:
        d=_reg(email.rsplit('@',1)[1])
        if not _bad_domain(d): return d
    intel=getattr(row,'company_intel',{}) or {}
    if isinstance(intel,dict):
        for src in intel.get('sources') or []:
            u=src.get('url') if isinstance(src,dict) else src; d=_reg(_host(u))
            if not _bad_domain(d): return d
    for field in ('target_url','url','source_url'):
        d=_reg(_host(getattr(row,field,'')))
        if not _bad_domain(d): return d
    return ''

def _score(intel):
    if not isinstance(intel,dict): return 0
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    score=0
    score += 60 if structured.get('founded_year') or structured.get('age_range') or structured.get('domain_age_label') else 0
    score += 60 if structured.get('size_range') else 0
    score += min(50,len([x for x in (intel.get('facts') or []) if isinstance(x,dict)])*5)
    score += min(20,len(intel.get('sources') or [])*2)
    try: score += int(intel.get('confidence') or 0)//4
    except Exception: pass
    return score

def _summary(intel):
    if not isinstance(intel,dict): return ''
    vals=[]
    for item in intel.get('facts') or []:
        if not isinstance(item,dict): continue
        label=str(item.get('label') or '').casefold(); val=' '.join(str(item.get('value') or '').split()).strip()
        if not val: continue
        if label in {'what they do','products/technology','products and technology','products','technology','actionability','potential work paths','engagement'}:
            if val.casefold() not in {x.casefold() for x in vals}: vals.append(val)
        if len(vals)>=2: break
    text=' '.join(vals).strip()
    return text[:2000]

def repair(apps,schema_editor):
    Opportunity=apps.get_model('portal','Opportunity'); Lead=apps.get_model('portal','CompanyLead'); Contact=apps.get_model('portal','Contact'); Cache=apps.get_model('portal','CompanyResearchCache')

    # Salary: remove qualitative/portal boilerplate and re-read numeric compensation from
    # retained JD/source evidence. No web or AI calls are performed in migrations.
    try:
        from portal.services.salary import salary_from_retained_opportunity, salary_text_has_numeric_amount
        fields=['salary_text','salary_currency','salary_min','salary_max','salary_period','salary_source_type','salary_source_url','salary_confidence','salary_checked_at']
        batch=[]
        for row in Opportunity.objects.all().iterator(chunk_size=200):
            current=str(row.salary_text or '')
            invalid=bool(current and (not salary_text_has_numeric_amount(current) or any(re.search(p,current,re.I|re.S) for p in NOISE)))
            info=salary_from_retained_opportunity(row)
            changed=False
            if info:
                for f in fields:
                    if f in info: setattr(row,f,info.get(f)); changed=True
            elif invalid:
                row.salary_text=''; row.salary_currency=''; row.salary_min=None; row.salary_max=None; row.salary_period=''; row.salary_source_type=''; row.salary_source_url=''; row.salary_confidence=0; changed=True
            if changed:
                batch.append(row)
                if len(batch)>=200:
                    Opportunity.objects.bulk_update(batch,fields,batch_size=200); batch=[]
        if batch: Opportunity.objects.bulk_update(batch,fields,batch_size=200)
    except Exception:
        pass

    # Re-run the reusable company-context copy after 0.8.103; many Cloud Hidden Leads were
    # created after that migration and therefore missed the original backfill.
    best_company={}; best_domain={}
    def consider(row,intel):
        if not isinstance(intel,dict) or not intel: return
        sc=_score(intel); ck=_key(getattr(row,'company','')); d=_domain(row)
        if ck and (ck not in best_company or sc>best_company[ck][0]): best_company[ck]=(sc,intel)
        if d and (d not in best_domain or sc>best_domain[d][0]): best_domain[d]=(sc,intel)
    for Model in (Opportunity,Lead,Contact):
        for row in Model.objects.all().iterator(chunk_size=300): consider(row,getattr(row,'company_intel',{}) or {})
    for cache in Cache.objects.all().iterator(chunk_size=300):
        intel=cache.data if isinstance(cache.data,dict) else {}
        if not intel: continue
        sc=_score(intel); ck=_key(cache.company); d=_reg(cache.domain)
        if ck and (ck not in best_company or sc>best_company[ck][0]): best_company[ck]=(sc,intel)
        if d and not _bad_domain(d) and (d not in best_domain or sc>best_domain[d][0]): best_domain[d]=(sc,intel)

    for Model in (Lead,Contact):
        batch=[]; fields=['company_intel']+(['company_summary'] if Model is Contact else [])
        for row in Model.objects.all().iterator(chunk_size=300):
            cur=row.company_intel if isinstance(row.company_intel,dict) else {}; ck=_key(row.company); d=_domain(row)
            cand=(best_company.get(ck) if ck else None) or (best_domain.get(d) if d else None)
            changed=False
            if cand and _score(cand[1])>_score(cur): row.company_intel=cand[1]; cur=cand[1]; changed=True
            if Model is Contact and not str(row.company_summary or '').strip():
                summ=_summary(cur)
                if summ: row.company_summary=summ; changed=True
            if changed:
                batch.append(row)
                if len(batch)>=300: Model.objects.bulk_update(batch,fields,batch_size=300); batch=[]
        if batch: Model.objects.bulk_update(batch,fields,batch_size=300)

class Migration(migrations.Migration):
    dependencies=[('portal','0064_v08104_portal_root_salary_repair')]
    operations=[migrations.RunPython(repair,migrations.RunPython.noop)]
