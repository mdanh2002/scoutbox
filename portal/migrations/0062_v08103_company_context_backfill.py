import re
from urllib.parse import urlsplit
from django.db import migrations

PLATFORMS={
    'linkedin.com','indeed.com','glassdoor.com','ziprecruiter.com','simplyhired.com','monster.com',
    'greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com',
    'jobstreet.com','jobsdb.com','wearedevelopers.com','facebook.com','reddit.com','x.com','twitter.com','youtube.com',
    'github.com','gitlab.com',
}
FREE={'gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com','icloud.com','proton.me','protonmail.com','aol.com'}
TWO={'co.uk','org.uk','com.au','net.au','co.nz','com.sg','com.my','co.jp','co.in','com.br','com.mx','co.za'}

def _host(url):
    try: return (urlsplit(str(url or '')).hostname or '').lower().removeprefix('www.')
    except Exception: return ''

def _reg(host):
    labels=[x for x in str(host or '').lower().strip('.').split('.') if x]
    if len(labels)<=2: return '.'.join(labels)
    return '.'.join(labels[-3:]) if '.'.join(labels[-2:]) in TWO else '.'.join(labels[-2:])

def _bad(d): return not d or d in FREE or any(d==x or d.endswith('.'+x) for x in PLATFORMS)
def _key(v): return re.sub(r'[^a-z0-9]+','',str(v or '').casefold())
def _unknown_company(v): return not str(v or '').strip() or str(v or '').strip().casefold() in {'unknown','unknown company','company','employer'}

def _domain(row):
    email=str(getattr(row,'contact_email',None) or getattr(row,'email','') or '').strip().lower()
    if '@' in email:
        d=_reg(email.rsplit('@',1)[1])
        if not _bad(d): return d
    intel=getattr(row,'company_intel',{}) or {}
    for src in intel.get('sources') or [] if isinstance(intel,dict) else []:
        u=src.get('url') if isinstance(src,dict) else src; d=_reg(_host(u))
        if not _bad(d): return d
    for field in ('target_url','url','source_url','contact_url'):
        d=_reg(_host(getattr(row,field,'')))
        if not _bad(d): return d
    return ''

def _intel_score(intel):
    if not isinstance(intel,dict): return 0
    st=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    score=0
    score+=20 if st.get('founded_year') else 0
    score+=18 if st.get('domain_age_label') else 0
    score+=18 if st.get('size_range') else 0
    score+=min(30,len([x for x in (intel.get('facts') or []) if isinstance(x,dict)])*3)
    score+=min(12,len(intel.get('sources') or [])*2)
    try: score+=min(20,int(intel.get('confidence') or 0)//5)
    except Exception: pass
    return score

def _summary(intel):
    if not isinstance(intel,dict): return ''
    preferred=[]; secondary=[]
    for item in intel.get('facts') or []:
        if not isinstance(item,dict): continue
        label=str(item.get('label') or '').casefold(); value=' '.join(str(item.get('value') or '').split()).strip()
        if not value: continue
        if label in {'what they do','products/technology','products and technology','products','technology'}: preferred.append(value)
        elif label in {'actionability','potential work paths','engagement'}: secondary.append(value)
    vals=[]
    for value in preferred+secondary:
        if value.casefold() not in {x.casefold() for x in vals}: vals.append(value)
        if len(vals)>=2: break
    text=' '.join(vals)
    return (text[:597].rsplit(' ',1)[0]+'…') if len(text)>600 else text


def _company_from_html(row):
    facts=getattr(row,'extracted_facts',{}) or {}
    html=str(facts.get('description_html') or '') if isinstance(facts,dict) else ''
    if not html: return ''
    # JSON-LD job postings commonly retain the true employer even when the visible URL
    # belongs to JobStreet/LinkedIn/an ATS. Restrict extraction to hiringOrganization so
    # a portal/publisher name cannot become the employer.
    m=re.search(r'"hiringOrganization"\s*:\s*\{.{0,1800}?"name"\s*:\s*"([^"\\]{2,220})"',html,re.I|re.S)
    if not m: return ''
    value=' '.join(m.group(1).replace('\\u0026','&').split()).strip()
    return value[:220] if value.casefold() not in {'unknown','unknown company','company','employer'} else ''

def _company_from_intel(intel):
    if not isinstance(intel,dict): return ''
    direct=' '.join(str(intel.get('company') or '').split()).strip()
    if direct and direct.casefold() not in {'unknown','unknown company','company','employer'}: return direct[:220]
    for item in intel.get('facts') or []:
        if isinstance(item,dict) and str(item.get('label') or '').strip().casefold() in {'company','employer','organisation','organization'}:
            value=' '.join(str(item.get('value') or '').split()).strip()
            if value and value.casefold() not in {'unknown','unknown company','company','employer'}: return value[:220]
    return ''

def backfill(apps,schema_editor):
    Opportunity=apps.get_model('portal','Opportunity'); Lead=apps.get_model('portal','CompanyLead'); Contact=apps.get_model('portal','Contact'); Cache=apps.get_model('portal','CompanyResearchCache')
    models=(Opportunity,Lead,Contact)
    best_company={}; best_domain={}; summary_company={}; summary_domain={}

    def consider(row,intel):
        if not isinstance(intel,dict) or not intel: return
        score=_intel_score(intel); company=getattr(row,'company','') or _company_from_intel(intel); key=_key(company); domain=_domain(row)
        if key and (key not in best_company or score>best_company[key][0]): best_company[key]=(score,intel)
        if domain and (domain not in best_domain or score>best_domain[domain][0]): best_domain[domain]=(score,intel)
        summ=_summary(intel)
        if summ:
            if key: summary_company.setdefault(key,summ)
            if domain: summary_domain.setdefault(domain,summ)

    # Existing entity research and reusable domain cache are both valid upgrade sources.
    for Model in models:
        for row in Model.objects.all().iterator(chunk_size=300): consider(row,getattr(row,'company_intel',{}) or {})
    for cache in Cache.objects.all().iterator(chunk_size=300):
        intel=cache.data if isinstance(cache.data,dict) else {}
        if not intel: continue
        score=_intel_score(intel); d=_reg(cache.domain)
        if d and not _bad(d) and (d not in best_domain or score>best_domain[d][0]): best_domain[d]=(score,intel)
        ck=_key(cache.company or _company_from_intel(intel))
        if ck and (ck not in best_company or score>best_company[ck][0]): best_company[ck]=(score,intel)
        summ=_summary(intel)
        if summ:
            if d: summary_domain.setdefault(d,summ)
            if ck: summary_company.setdefault(ck,summ)

    for Model in (Opportunity,Lead):
        updates=[]
        fields=['company_intel']
        if Model is Opportunity: fields.append('company')
        for row in Model.objects.all().iterator(chunk_size=300):
            current=row.company_intel if isinstance(row.company_intel,dict) else {}; key=_key(getattr(row,'company','')); domain=_domain(row)
            candidate=(best_company.get(key) if key else None) or (best_domain.get(domain) if domain else None)
            changed=False
            if candidate and _intel_score(candidate[1])>_intel_score(current): row.company_intel=candidate[1]; current=candidate[1]; changed=True
            elif not current and domain:
                company_name=str(getattr(row,'company','') or '').strip()
                current={'company':company_name,'confidence':20,'facts':([{'label':'Company','value':company_name}] if company_name else [])+[{'label':'Website','value':'https://'+domain+'/'}],
                         'structured':{'domain_age_refresh_needed':True},'sources':[{'title':'Stored company domain','url':'https://'+domain+'/'}],
                         'errors':[],'status':'collecting'}
                row.company_intel=current; changed=True
            # Recover employer names only from stored company research, never from ATS/job-board hostnames.
            if Model is Opportunity and _unknown_company(row.company):
                name=_company_from_intel(current) or _company_from_html(row)
                if name: row.company=name; changed=True
            if changed:
                updates.append(row)
                if len(updates)>=300: Model.objects.bulk_update(updates,fields,batch_size=300); updates=[]
        if updates: Model.objects.bulk_update(updates,fields,batch_size=300)

    updates=[]
    for row in Contact.objects.all().iterator(chunk_size=300):
        current=row.company_intel if isinstance(row.company_intel,dict) else {}; key=_key(row.company); domain=_domain(row)
        candidate=(best_company.get(key) if key else None) or (best_domain.get(domain) if domain else None)
        changed=False
        if candidate and _intel_score(candidate[1])>_intel_score(current): row.company_intel=candidate[1]; current=candidate[1]; changed=True
        elif not current and domain:
            current={'company':row.company or '','confidence':20,'facts':([{'label':'Company','value':row.company}] if row.company else [])+[{'label':'Website','value':'https://'+domain+'/'}],
                     'structured':{'domain_age_refresh_needed':True},'sources':[{'title':'Address Book domain','url':'https://'+domain+'/'}],
                     'errors':[],'status':'collecting'}
            row.company_intel=current; changed=True
        if _unknown_company(row.company):
            name=_company_from_intel(current)
            if name: row.company=name[:200]; key=_key(row.company); changed=True
        if not str(row.company_summary or '').strip():
            summ=_summary(current) or summary_company.get(key,'') or summary_domain.get(domain,'')
            if summ: row.company_summary=summ[:2000]; changed=True
        if changed:
            updates.append(row)
            if len(updates)>=300: Contact.objects.bulk_update(updates,['company','company_intel','company_summary'],batch_size=300); updates=[]
    if updates: Contact.objects.bulk_update(updates,['company','company_intel','company_summary'],batch_size=300)

def noop(apps,schema_editor): pass

class Migration(migrations.Migration):
    dependencies=[('portal','0061_v08103_salary_backfill')]
    operations=[migrations.RunPython(backfill,noop)]
