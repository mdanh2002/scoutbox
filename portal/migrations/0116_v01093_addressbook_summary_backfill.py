import re
from django.db import migrations
from django.db.models import Q


def _summary_from_intel(intel):
    if not isinstance(intel, dict):
        return ''
    preferred=[]; secondary=[]
    for row in intel.get('facts') or []:
        if not isinstance(row,dict):
            continue
        label=str(row.get('label') or '').strip().casefold()
        value=' '.join(str(row.get('value') or '').split()).strip()
        if not value:
            continue
        if label in {'what they do','products/technology','products and technology','products','technology'}:
            preferred.append(value)
        elif label in {'actionability','potential work paths','engagement'}:
            secondary.append(value)
    return ' '.join((preferred+secondary)[:2])[:2000]


def _company_sentence(company, *texts):
    company_tokens=[x for x in re.findall(r'[a-z0-9]+',str(company or '').casefold()) if len(x)>=4 and x not in {'company','technology','technologies','solutions','systems','group','labs'}]
    org_verbs=('builds','develops','designs','manufactures','provides','offers','creates','makes','operates','specializes','specialises','platform','products','services','solutions','customers')
    noise=('responsibilities','requirements','candidate will','you will','the role','job description','years of experience','apply now')
    text=' '.join(str(x or '') for x in texts if str(x or '').strip())[:18000]
    rows=[]
    for sentence in re.split(r'(?<=[.!?])\s+|\n+',re.sub(r'\s+',' ',text)):
        clean=' '.join(sentence.split()).strip(' -–—|')
        if len(clean)<25 or len(clean)>520:
            continue
        low=clean.casefold()
        if any(x in low for x in noise) or not any(x in low for x in org_verbs):
            continue
        hit=bool(company_tokens and any(t in low for t in company_tokens[:5]))
        rows.append(((2 if hit else 0)+(1 if len(clean)<=260 else 0),clean))
    rows.sort(key=lambda x:x[0],reverse=True)
    return rows[0][1][:2000] if rows else ''


def backfill(apps, schema_editor):
    Contact=apps.get_model('portal','Contact')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    updates=[]
    for contact in Contact.objects.filter(company_summary='').iterator(chunk_size=200):
        company=' '.join(str(contact.company or '').split()).strip()
        email=str(contact.email or '').strip()
        q=Q()
        if company:
            q|=Q(company__iexact=company)
        if email:
            q|=Q(contact_email__iexact=email)
        summary=''
        if q.children:
            lead=CompanyLead.objects.filter(q,user_deleted=False).order_by('-updated_at').first()
            if lead:
                summary=' '.join(str(lead.summary or '').split()).strip() or _summary_from_intel(lead.company_intel or {})
                if not summary:
                    summary=_company_sentence(company,lead.evidence,lead.match_summary)
            if not summary:
                opp=Opportunity.objects.filter(q,user_deleted=False).order_by('-updated_at').first()
                if opp:
                    summary=_summary_from_intel(opp.company_intel or {})
                    if not summary:
                        summary=_company_sentence(company,opp.raw_search_snippet,opp.recommendation_reason,opp.list_highlight,opp.description)
        if summary:
            contact.company_summary=summary[:2000]
            updates.append(contact)
            if len(updates)>=200:
                Contact.objects.bulk_update(updates,['company_summary'],batch_size=200); updates=[]
    if updates:
        Contact.objects.bulk_update(updates,['company_summary'],batch_size=200)


class Migration(migrations.Migration):
    dependencies=[('portal','0115_v01091_company_identity_repair')]
    operations=[migrations.RunPython(backfill,migrations.RunPython.noop)]
