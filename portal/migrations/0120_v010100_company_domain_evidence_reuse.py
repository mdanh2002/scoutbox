import re
from datetime import date, datetime
from django.db import migrations


LEGAL = {'inc','llc','ltd','limited','corp','corporation','company','co','gmbh','plc','pty','group','holdings'}
GENERIC = {'technologies','technology','systems','solutions','network','networks'}


def _identity_key(value):
    words=[x for x in re.findall(r'[a-z0-9]+', str(value or '').casefold()) if x not in LEGAL and x not in GENERIC]
    return ''.join(words)


def _registrable_domain(raw):
    text=str(raw or '').strip().lower()
    text=re.sub(r'^https?://','',text).split('/',1)[0].split(':',1)[0].strip('.').removeprefix('www.')
    labels=[x for x in text.split('.') if x]
    if len(labels)<2:
        return ''
    two={'co.uk','org.uk','com.au','net.au','co.nz','com.sg','com.my','co.jp','co.in','com.br','com.mx','co.za'}
    tail='.'.join(labels[-2:])
    return '.'.join(labels[-3:]) if len(labels)>=3 and tail in two else tail


def _domain_matches(company, domain):
    key=_identity_key(company)
    domain=_registrable_domain(domain)
    stem=re.sub(r'[^a-z0-9]','',domain.split('.')[0]) if domain else ''
    if not key or not stem:
        return False
    if key==stem:
        return True
    if key in stem and len(key)>=4 and len(key)/max(1,len(stem))>=0.70:
        return True
    if stem in key and len(stem)>=4 and len(stem)/max(1,len(key))>=0.75:
        return True
    return False


def _extract(intel):
    intel=intel if isinstance(intel,dict) else {}
    st=dict(intel.get('structured') or {}) if isinstance(intel.get('structured'),dict) else {}
    for key in ('domain_age_domain','domain_registered_at','domain_age_years','domain_age_label'):
        if st.get(key) in (None,'') and intel.get(key) not in (None,''):
            st[key]=intel.get(key)
    for fact in intel.get('facts') or []:
        if not isinstance(fact,dict):
            continue
        label=str(fact.get('label') or '').strip().casefold().replace('_',' ')
        if label not in {'domain age','domain created','domain creation','domain registered','domain registration','domain registration date'}:
            continue
        value=str(fact.get('value') or '').strip()
        if not st.get('domain_age_domain'):
            m=re.search(r'(?i)\b(?:https?://)?(?:www\.)?([a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+)\b',value)
            if m: st['domain_age_domain']=m.group(1).lower()
        if not st.get('domain_registered_at'):
            m=re.search(r'\b((?:18|19|20)\d{2}-\d{2}-\d{2})\b',value)
            if m: st['domain_registered_at']=m.group(1)
            else:
                m=re.search(r'(?i)\b(?:registered|created|creation|since)\D{0,12}((?:18|19|20)\d{2})\b',value)
                if m: st['domain_registered_at']=m.group(1)
        if st.get('domain_age_years') in (None,''):
            if re.search(r'(?i)\b<\s*1\s*(?:yr|yrs|year|years)\b',value):
                st['domain_age_years']=0
            else:
                m=re.search(r'(?i)(?<!\d)(\d{1,3})\s*(?:yr|yrs|year|years)\b',value)
                if m: st['domain_age_years']=int(m.group(1))
    domain=_registrable_domain(st.get('domain_age_domain'))
    registered=str(st.get('domain_registered_at') or '').strip()
    years=st.get('domain_age_years')
    try: years=None if years in (None,'') else max(0,int(float(years)))
    except Exception: years=None
    if years is None and registered:
        try:
            dt=datetime.fromisoformat(registered[:10]).date()
            today=date.today(); years=max(0,today.year-dt.year-((today.month,today.day)<(dt.month,dt.day)))
        except Exception:
            m=re.search(r'\b(18|19|20)\d{2}\b',registered)
            if m: years=max(0,date.today().year-int(m.group(0)))
    label=str(st.get('domain_age_label') or '').strip()
    if not label and years is not None:
        label='<1 yr' if years<1 else (f'{years} yr' if years==1 else f'{years} yrs')
    return {'domain':domain,'registered':registered,'years':years,'label':label}


def _score(ev):
    return (100 if ev.get('registered') else 0)+(30 if ev.get('years') is not None else 0)+(10 if ev.get('domain') else 0)


def reuse_known_domain_evidence(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    Cache=apps.get_model('portal','CompanyResearchCache')
    models=(Opportunity,CompanyLead,Contact)

    best={}
    def consider(company,intel):
        key=_identity_key(company)
        if len(key)<4:
            return
        ev=_extract(intel)
        if not ev.get('domain') or not _domain_matches(company,ev.get('domain')):
            return
        if _score(ev)>_score(best.get(key,{})):
            best[key]=ev

    for row in Cache.objects.all().iterator():
        consider(getattr(row,'company',''),getattr(row,'data',{}) or {})
    for Model in models:
        for row in Model.objects.exclude(company_intel={}).iterator():
            consider(getattr(row,'company',''),getattr(row,'company_intel',{}) or {})

    for Model in models:
        for row in Model.objects.exclude(company_intel={}).iterator():
            company=str(getattr(row,'company','') or '').strip(); key=_identity_key(company)
            ev=best.get(key)
            if not ev:
                continue
            intel=dict(row.company_intel or {}) if isinstance(row.company_intel,dict) else {}
            st=dict(intel.get('structured') or {}) if isinstance(intel.get('structured'),dict) else {}
            current=_extract(intel)
            current_good=bool(current.get('domain') and _domain_matches(company,current.get('domain')) and current.get('registered'))
            if current_good and current.get('domain')==ev.get('domain'):
                continue
            changed=False
            for key_name,value in (
                ('domain_age_domain',ev.get('domain')),
                ('domain_registered_at',ev.get('registered')),
                ('domain_age_years',ev.get('years')),
                ('domain_age_label',ev.get('label')),
            ):
                if value not in (None,'') and st.get(key_name)!=value:
                    st[key_name]=value; changed=True
            existing_company_domain=_registrable_domain(st.get('company_domain'))
            if ev.get('domain') and (not existing_company_domain or not _domain_matches(company,existing_company_domain)):
                st['company_domain']=ev['domain']; changed=True
            if ev.get('registered'):
                if st.pop('domain_age_refresh_needed',None) is not None: changed=True
                if st.pop('domain_age_checked_at',None) is not None: changed=True
            if not changed:
                continue
            facts=[dict(x) for x in (intel.get('facts') or []) if isinstance(x,dict) and str(x.get('label') or '').strip().casefold()!='domain age']
            facts.append({'label':'Domain Age','value':f"{ev.get('label') or ''} ({ev.get('domain')}; registered {ev.get('registered')})".strip(),'verification':'domain-registration'})
            intel['facts']=facts[:12]; intel['structured']=st
            row.company_intel=intel
            row.save(update_fields=['company_intel'])

    # Keep the reusable cache coherent too, so new sibling records inherit the same facts.
    for row in Cache.objects.all().iterator():
        company=str(getattr(row,'company','') or '').strip(); ev=best.get(_identity_key(company))
        if not ev:
            continue
        data=dict(row.data or {}) if isinstance(row.data,dict) else {}
        st=dict(data.get('structured') or {}) if isinstance(data.get('structured'),dict) else {}
        changed=False
        for key_name,value in (
            ('domain_age_domain',ev.get('domain')),('domain_registered_at',ev.get('registered')),
            ('domain_age_years',ev.get('years')),('domain_age_label',ev.get('label')),
        ):
            if value not in (None,'') and st.get(key_name)!=value:
                st[key_name]=value; changed=True
        if changed:
            st.pop('domain_age_refresh_needed',None); data['structured']=st; row.data=data; row.save(update_fields=['data'])


class Migration(migrations.Migration):
    dependencies=[('portal','0119_v01098_company_domain_tooltip_repair')]
    operations=[migrations.RunPython(reuse_known_domain_evidence,migrations.RunPython.noop)]
