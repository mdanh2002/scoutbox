from django.db import migrations
import datetime
import json
import re

EMAIL_RE = re.compile(r'(?i)(?<![A-Z0-9._%+\-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![A-Z0-9._%+\-])')
NON_CONTACT = ('noreply','no-reply','donotreply','do-not-reply','privacy','legal','compliance','gdpr','dpo','abuse')
GENERIC = {'info','jobs','careers','contact','hello','office','support','hr','recruiting','recruitment'}


def _company_key(value):
    return re.sub(r'[^a-z0-9]+','',str(value or '').lower())


def _text(*values):
    out=[]
    for value in values:
        if isinstance(value,(dict,list,tuple)):
            try: value=json.dumps(value,ensure_ascii=False,default=str)
            except Exception: value=str(value)
        if value: out.append(str(value))
    return '\n'.join(out)


def _candidate_email(*values):
    found=[]
    for email in EMAIL_RE.findall(_text(*values)):
        email=email.strip('.,;:<>[](){}').lower()
        local=email.split('@',1)[0]
        compact=re.sub(r'[^a-z0-9]+','',local)
        if any(re.sub(r'[^a-z0-9]+','',x) in compact for x in NON_CONTACT):
            continue
        if email not in found: found.append(email)
    if not found: return ''
    found.sort(key=lambda x:(x.split('@',1)[0] in GENERIC, x))
    return found[0]


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
        m=re.search(r'(?i)(?<!\d)(1\s*[–-]\s*10|10\s*[–-]\s*20|20\s*[–-]\s*50|50\s*[–-]\s*100)(?!\d)(?:\s+(?:employees?|people|staff|team members?))?',blob)
        if m: size=re.sub(r'\s*[–-]\s*','–',m.group(1))
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
    current['facts']=facts[:12]
    if (year or founder or size) and not current.get('status'): current['status']='backfilled'
    return current


def backfill_existing_records(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')

    # First pass: repair structured contact_email from public data already saved on the row.
    for row in Opportunity.objects.filter(contact_email='').iterator():
        email=_candidate_email(row.note,row.description,row.raw_search_snippet,row.extracted_facts,row.company_intel)
        if email:
            Opportunity.objects.filter(pk=row.pk,contact_email='').update(contact_email=email)
    for row in CompanyLead.objects.filter(contact_email='').iterator():
        email=_candidate_email(row.note,row.summary,row.match_summary,row.evidence,row.evidence_translation,row.company_intel)
        if email:
            CompanyLead.objects.filter(pk=row.pk,contact_email='').update(contact_email=email)

    # Build the best known Company Info per company, using only already-stored evidence.
    best={}
    def quality(intel):
        st=intel.get('structured') if isinstance(intel,dict) and isinstance(intel.get('structured'),dict) else {}
        return sum(bool(st.get(k)) for k in ('founded_year','founded_by','age_range','size_range')) + min(3,len(intel.get('sources') or []) if isinstance(intel,dict) else 0)

    for row in Opportunity.objects.all().iterator():
        intel=_infer_company_intel(row.company,row.company_intel,row.description,row.raw_search_snippet,row.extracted_facts,row.note)
        Opportunity.objects.filter(pk=row.pk).update(company_intel=intel)
        key=_company_key(row.company)
        if key and (key not in best or quality(intel)>quality(best[key])): best[key]=intel
    for row in CompanyLead.objects.all().iterator():
        intel=_infer_company_intel(row.company,row.company_intel,row.summary,row.match_summary,row.evidence,row.evidence_translation,row.note)
        CompanyLead.objects.filter(pk=row.pk).update(company_intel=intel)
        key=_company_key(row.company)
        if key and (key not in best or quality(intel)>quality(best[key])): best[key]=intel
    for row in Contact.objects.all().iterator():
        key=_company_key(row.company)
        base=row.company_intel if isinstance(row.company_intel,dict) else {}
        if key in best and quality(best[key])>quality(base):
            base=dict(best[key])
        intel=_infer_company_intel(row.company,base,row.company_summary,row.notes)
        Contact.objects.filter(pk=row.pk).update(company_intel=intel)

    # Second pass shares stronger stored Company Info across duplicate company records.
    for Model in (Opportunity,CompanyLead,Contact):
        for row in Model.objects.all().iterator():
            key=_company_key(getattr(row,'company',''))
            if not key or key not in best: continue
            current=getattr(row,'company_intel',{}) or {}
            if quality(best[key])>quality(current):
                Model.objects.filter(pk=row.pk).update(company_intel=best[key])


class Migration(migrations.Migration):
    dependencies=[('portal','0048_v0881_clean_cloud_outreach_notes')]
    operations=[migrations.RunPython(backfill_existing_records,migrations.RunPython.noop)]
