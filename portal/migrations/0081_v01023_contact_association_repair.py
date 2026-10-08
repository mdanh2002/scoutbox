import re

from django.db import migrations


BAD_CONTACT_EMAILS={'taops@marvell.com','help.join@vertiv.com'}


def _clean_email(value):
    return str(value or '').strip().lower()


def _scrub_exact_contact_values(value):
    """Blank exact bad-email values in structured metadata, preserving raw source text."""
    changed=False
    if isinstance(value,dict):
        out={}
        for key,item in value.items():
            cleaned,item_changed=_scrub_exact_contact_values(item)
            out[key]=cleaned
            changed=changed or item_changed
        return out,changed
    if isinstance(value,list):
        out=[]
        for item in value:
            cleaned,item_changed=_scrub_exact_contact_values(item)
            out.append(cleaned)
            changed=changed or item_changed
        return out,changed
    if isinstance(value,str) and _clean_email(value) in BAD_CONTACT_EMAILS:
        return '',True
    return value,False


def _linkedin_company(text):
    raw=str(text or '')
    if not raw:
        return ''
    patterns=(
        r'(?im)^\s*role at\s*$\s*^\s*([^\r\n]{2,220})\s*$',
        r'(?im)^\s*See who\s+(.+?)\s+has hired for this role\s*$',
        r'(?is)\brole at\s*[\r\n]+\s*([^\r\n]{2,220})',
    )
    for pattern in patterns:
        m=re.search(pattern,raw)
        if not m:
            continue
        company=' '.join(m.group(1).split()).strip(' -–—|:')[:220]
        if company and company.casefold() not in {'linkedin','apply','sign in','join now'}:
            return company
    lines=[' '.join(line.split()).strip() for line in raw.splitlines()]
    lines=[line for line in lines if line]
    if len(lines)>=3:
        company=lines[1].strip(' -–—|:')[:220]
        if company and company.casefold() not in {'linkedin','apply','sign in','join now'}:
            return company
    return ''


def repair(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    ImportCandidate=apps.get_model('portal','ImportCandidate')

    # Known accommodation/helpdesk addresses were previously allowed into structured
    # contact fields and then propagated between unrelated aggregator-hosted records.
    for bad in BAD_CONTACT_EMAILS:
        Opportunity.objects.filter(contact_email__iexact=bad).update(contact_email='')
        CompanyLead.objects.filter(contact_email__iexact=bad).update(contact_email='')
        ImportCandidate.objects.filter(email__iexact=bad).update(email='')
        Contact.objects.filter(email__iexact=bad).delete()

    # Remove exact bad-email values from contact metadata while retaining the original
    # job description/page HTML. The latter is evidence explaining why the address was
    # rejected and should not be rewritten by a data repair migration.
    for row in Opportunity.objects.only('pk','extracted_facts','company_intel','company','description','target_url','canonical_url','url','search_url').iterator(chunk_size=200):
        updates={}
        for field in ('extracted_facts','company_intel'):
            current=getattr(row,field,None)
            cleaned,changed=_scrub_exact_contact_values(current)
            if changed:
                updates[field]=cleaned
        url=str(row.target_url or row.canonical_url or row.url or row.search_url or '').lower()
        if str(row.company or '').strip().casefold() in {'linkedin','linkedin.com'} and 'linkedin.com/' in url:
            employer=_linkedin_company(row.description)
            if employer:
                updates['company']=employer
        if updates:
            Opportunity.objects.filter(pk=row.pk).update(**updates)

    for row in CompanyLead.objects.only('pk','ai_state','company_intel','company','evidence','summary','match_summary','target_url','source_url','search_url').iterator(chunk_size=200):
        updates={}
        for field in ('ai_state','company_intel'):
            current=getattr(row,field,None)
            cleaned,changed=_scrub_exact_contact_values(current)
            if changed:
                updates[field]=cleaned
        url=str(row.target_url or row.source_url or row.search_url or '').lower()
        if str(row.company or '').strip().casefold() in {'linkedin','linkedin.com'} and 'linkedin.com/' in url:
            employer=_linkedin_company('\n'.join(str(x or '') for x in (row.evidence,row.summary,row.match_summary)))
            if employer:
                updates['company']=employer
        if updates:
            CompanyLead.objects.filter(pk=row.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies=[('portal','0080_v0963_addressbook_autopersist_repair')]
    operations=[migrations.RunPython(repair,migrations.RunPython.noop)]
