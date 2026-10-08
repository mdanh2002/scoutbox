from django.db import migrations
from django.utils import timezone
import datetime
import json
import re

EMAIL_RE = re.compile(r'(?i)(?<![A-Z0-9._%+\-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![A-Z0-9._%+\-])')
NON_CONTACT = {
    'noreply','no-reply','donotreply','do-not-reply','privacy','privacyoffice','legal','compliance','gdpr','dpo',
    'dataprotection','abuse','security','securityteam','press','media','investorrelations','dmca','copyright','mailerdaemon',
}
GENERIC = {
    'contact','contacts','sales','support','help','service','customerservice','jobs','job','careers','career','info','hello',
    'recruiting','recruitment','talent','hr','humanresources','people','admin','office','team','billing','enquiries','inquiries',
    'apply','application','applications','hiring',
}
REGION = {
    'singapore','sg','apac','asia','sea','southeastasia','emea','europe','eu','uk','unitedkingdom','usa','us','unitedstates',
    'canada','ca','australia','au','anz','newzealand','nz','india','japan','jp','korea','kr','china','cn','hongkong','hk',
    'taiwan','tw','malaysia','my','indonesia','id','thailand','th','vietnam','vn','philippines','ph','mexico','mx','brazil',
    'br','latam','germany','de','france','fr','spain','es','italy','it','netherlands','nl','sweden','se','norway','no',
}


def _company_key(value):
    return re.sub(r'[^a-z0-9]+','',str(value or '').lower())


def _compact_local(email):
    local=(str(email or '').lower().split('@',1)[0].split('+',1)[0] if '@' in str(email or '') else str(email or '').lower())
    return re.sub(r'[^a-z0-9]+','',local)


def _is_non_contact(email):
    compact=_compact_local(email)
    return any(re.sub(r'[^a-z0-9]+','',x) in compact for x in NON_CONTACT)


def _is_region(email):
    raw=str(email or '').lower()
    local=raw.split('@',1)[0].split('+',1)[0] if '@' in raw else raw
    compact=re.sub(r'[^a-z0-9]+','',local)
    if compact in REGION:
        return True
    tokens=[re.sub(r'[^a-z0-9]+','',x) for x in re.split(r'[._-]+',local) if x]
    return any(t in REGION and len(t)>=2 for t in tokens)


def _is_generic(email):
    if _is_non_contact(email):
        return True
    raw=str(email or '').lower()
    local=raw.split('@',1)[0].split('+',1)[0] if '@' in raw else raw
    compact=re.sub(r'[^a-z0-9]+','',local)
    if any(x in compact for x in ('noreply','donotreply','mailerdaemon')):
        return True
    return compact in {re.sub(r'[^a-z0-9]+','',x) for x in GENERIC} or any(compact.startswith(re.sub(r'[^a-z0-9]+','',x)) for x in GENERIC if len(x)>=4)


def _text(*values):
    out=[]
    for value in values:
        if isinstance(value,(dict,list,tuple)):
            try: value=json.dumps(value,ensure_ascii=False,default=str)
            except Exception: value=str(value)
        if value: out.append(str(value))
    return '\n'.join(out)


def _emails(*values):
    found=[]
    for email in EMAIL_RE.findall(_text(*values)):
        email=email.strip('.,;:<>[](){}').lower()
        if not _is_non_contact(email) and email not in found:
            found.append(email)
    return found


def _email_quality(email, name=''):
    if not email or _is_non_contact(email): return -100
    score=10
    if _is_region(email): score+=45
    elif _is_generic(email): score-=20
    else: score+=55
    if str(name or '').strip(): score+=10
    return score


def _best_email(candidates):
    rows=[(e,n) for e,n in candidates if e and not _is_non_contact(e)]
    if not rows: return ''
    rows.sort(key=lambda x:(-_email_quality(x[0],x[1]),x[0]))
    return rows[0][0]


def _age_band(year):
    try: years=max(0,datetime.date.today().year-int(year))
    except Exception: return ''
    if years < 1: return '<1 yr'
    if years < 3: return '1–3 yr'
    if years < 5: return '3–5 yr'
    if years < 10: return '5–10 yr'
    return '10+ yr'


def _infer_company_intel(company, current, *values):
    current=dict(current or {}) if isinstance(current,dict) else {}
    structured=dict(current.get('structured') or {}) if isinstance(current.get('structured'),dict) else {}
    facts=[dict(x) for x in (current.get('facts') or []) if isinstance(x,dict)]
    blob=_text(current,*values)

    year=structured.get('founded_year') or ''
    if not year:
        m=re.search(r'(?i)\b(?:founded|established|started|since)\s*(?:in\s*)?((?:18|19|20)\d{2})\b',blob)
        if m: year=int(m.group(1))
    size=str(structured.get('size_range') or '').strip()
    if not size:
        m=re.search(r'(?i)(?<!\d)(1\s*[–-]\s*10|10\s*[–-]\s*20|20\s*[–-]\s*50|50\s*[–-]\s*100|100\s*\+)(?!\d)(?:\s+(?:employees?|people|staff|team members?))?',blob)
        if m: size=re.sub(r'\s*[–-]\s*','–',m.group(1)).replace('100 +','100+')
    founder=str(structured.get('founded_by') or '').strip()
    if not founder:
        m=re.search(r'(?i)\b(?:founded|co-founded)\s+by\s+([A-Z][A-Za-z .\'’\-]{2,80})(?=[,.;\n]|\s+(?:in|and)\b|$)',blob)
        if m: founder=m.group(1).strip()
    age=str(structured.get('age_range') or '').strip() or (_age_band(year) if year else '')
    structured.update({'founded_year':year or '', 'founded_by':founder, 'age_range':age, 'size_range':size})

    labels={str(x.get('label') or '').casefold() for x in facts}
    if year and 'founded' not in labels: facts.append({'label':'Founded','value':str(year),'verification':'estimate'})
    if founder and 'founded by' not in labels: facts.append({'label':'Founded by','value':founder,'verification':'estimate'})
    if size and not any(('size' in x or 'employee' in x) for x in labels): facts.append({'label':'Company size','value':size,'verification':'estimate'})
    if company and not current.get('company'): current['company']=company
    current['structured']=structured
    current['facts']=facts[:16]
    if (year or founder or size) and not current.get('status'): current['status']='backfilled'
    # Recovered/inferred values are not upgraded to high confidence merely because they exist.
    if (year or founder or size) and not current.get('confidence'): current['confidence']=55
    return current


def _intel_quality(intel):
    if not isinstance(intel,dict): return 0
    st=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    score=sum(bool(st.get(k)) for k in ('founded_year','founded_by','age_range','size_range'))*3
    score+=min(4,len(intel.get('sources') or []))
    try: score+=int(intel.get('confidence') or 0)//30
    except Exception: pass
    return score


def _strip_email_only_note(note):
    kept=[]
    for raw in str(note or '').splitlines():
        line=raw.strip()
        if not line: continue
        if re.fullmatch(r'(?i)(?:contact\s+)?email\s*:\s*[^@\s]+@[^@\s]+\.[^@\s]+[.,;]?',line): continue
        if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+[.,;]?',line): continue
        kept.append(line)
    return '\n'.join(kept).strip()


def backfill_v0883(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')

    # Rebuild Company Info from already stored evidence, then share the strongest
    # stored result across records belonging to the same normalized company.
    best={}
    for row in Opportunity.objects.all().iterator():
        intel=_infer_company_intel(row.company,row.company_intel,row.description,row.raw_search_snippet,row.extracted_facts,row.note)
        Opportunity.objects.filter(pk=row.pk).update(company_intel=intel)
        key=_company_key(row.company)
        if key and _intel_quality(intel)>_intel_quality(best.get(key)): best[key]=intel
    for row in CompanyLead.objects.all().iterator():
        intel=_infer_company_intel(row.company,row.company_intel,row.summary,row.match_summary,row.evidence,row.evidence_translation,row.note,row.ai_state)
        CompanyLead.objects.filter(pk=row.pk).update(company_intel=intel)
        key=_company_key(row.company)
        if key and _intel_quality(intel)>_intel_quality(best.get(key)): best[key]=intel
    for row in Contact.objects.all().iterator():
        intel=_infer_company_intel(row.company,row.company_intel,row.company_summary,row.notes)
        key=_company_key(row.company)
        if key and _intel_quality(best.get(key))>_intel_quality(intel): intel=dict(best[key])
        Contact.objects.filter(pk=row.pk).update(company_intel=intel)
        if key and _intel_quality(intel)>_intel_quality(best.get(key)): best[key]=intel
    for Model in (Opportunity,CompanyLead,Contact):
        for row in Model.objects.all().iterator():
            key=_company_key(getattr(row,'company',''))
            current=getattr(row,'company_intel',{}) or {}
            if key and key in best and _intel_quality(best[key])>_intel_quality(current):
                Model.objects.filter(pk=row.pk).update(company_intel=best[key])

    # Build a same-company email pool from every already-stored source. Functional
    # mailboxes are allowed on Opportunity/Lead records, even though Address Book is stricter.
    pool={}
    def collect(company,email,name=''):
        key=_company_key(company)
        email=str(email or '').strip().lower()
        if key and email and not _is_non_contact(email): pool.setdefault(key,[]).append((email,name))
    for row in Contact.objects.filter(deleted_at__isnull=True).iterator(): collect(row.company,row.email,row.name)
    for row in Opportunity.objects.all().iterator():
        collect(row.company,row.contact_email,'')
        for e in _emails(row.note,row.description,row.raw_search_snippet,row.extracted_facts,row.company_intel): collect(row.company,e,'')
    for row in CompanyLead.objects.all().iterator():
        collect(row.company,row.contact_email,row.contact_name)
        for e in _emails(row.note,row.summary,row.match_summary,row.evidence,row.evidence_translation,row.company_intel,row.ai_state): collect(row.company,e,row.contact_name)

    for row in Opportunity.objects.filter(contact_email='').iterator():
        own=[(e,'') for e in _emails(row.note,row.description,row.raw_search_snippet,row.extracted_facts,row.company_intel)]
        email=_best_email(own + pool.get(_company_key(row.company),[]))
        if email: Opportunity.objects.filter(pk=row.pk,contact_email='').update(contact_email=email)
    for row in CompanyLead.objects.all().iterator():
        if not row.contact_email:
            own=[(e,row.contact_name) for e in _emails(row.note,row.summary,row.match_summary,row.evidence,row.evidence_translation,row.company_intel,row.ai_state)]
            email=_best_email(own + pool.get(_company_key(row.company),[]))
            if email: CompanyLead.objects.filter(pk=row.pk,contact_email='').update(contact_email=email)
        cleaned=_strip_email_only_note(row.note)
        if cleaned != (row.note or ''):
            CompanyLead.objects.filter(pk=row.pk).update(note=cleaned)

    # Address Book automatic collection is intentionally person/region-only. Existing
    # generic automatic contacts are moved to Recycle Bin rather than hard-deleted.
    now=timezone.now()
    for row in Contact.objects.filter(deleted_at__isnull=True).iterator():
        source=str(row.source or '').strip().casefold()
        if source=='manual':
            continue
        email=str(row.email or '').strip().lower()
        if _is_non_contact(email) or (_is_generic(email) and not _is_region(email)):
            Contact.objects.filter(pk=row.pk,deleted_at__isnull=True).update(deleted_at=now,is_read=True)
        elif _is_region(email) and row.generic:
            Contact.objects.filter(pk=row.pk).update(generic=False)


class Migration(migrations.Migration):
    dependencies=[('portal','0049_v0881_backfill_company_contact')]
    operations=[migrations.RunPython(backfill_v0883,migrations.RunPython.noop)]
