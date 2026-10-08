import re
from django.db import migrations


def _jobicy_region_from_html(html):
    raw=str(html or '')
    match=re.search(r'(?is)<dt[^>]*>\s*Remote\s+from\s*</dt>\s*<dd[^>]*>\s*(?:<a[^>]+job-region/[^>]*>)?\s*([^<]{2,120})',raw)
    if not match:
        return ''
    value=' '.join(match.group(1).split()).strip(' .,:;|/\\')
    aliases={
        'emea':'EMEA','apac':'APAC','europe':'Europe','eu':'EU','eea':'EEA','eu/eea':'EU/EEA',
        'mena':'MENA','gcc':'GCC','latam':'LATAM','north america':'North America',
        'south america':'South America','americas':'Americas','asia':'Asia','africa':'Africa',
        'anz':'ANZ','asean':'ASEAN','dach':'DACH','cee':'CEE','benelux':'Benelux','nordics':'Nordics',
    }
    return aliases.get(value.casefold(),'')


def forwards(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    Contact=apps.get_model('portal','Contact')
    AuditLog=apps.get_model('portal','AuditLog')

    repaired_urls={}
    for row in Opportunity.objects.filter(url__icontains='jobicy.com/jobs/').iterator(chunk_size=100):
        facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
        region=_jobicy_region_from_html(facts.get('description_html'))
        if not region:
            continue
        old_locations=row.locations if isinstance(row.locations,list) else []
        expanded=len(old_locations)>4 or len(str(row.country or ''))>70
        if not expanded and str(row.country or '').strip()==region and str(row.role_location or '').strip()==region:
            continue
        item={'kind':'region','label':region,'code':region.replace(' ','_').upper(),'icon':'','source':'jobicy_snapshot_html','evidence':f'Remote from {region}'}
        row.country=region
        row.role_location=region
        row.locations=[item]
        provenance=dict(facts.get('country_provenance') or {})
        provenance.update({'country':region,'locations':[item],'source':'jobicy_snapshot_html','evidence':f'Remote from {region}','fallback':False,'policy':'0.11.93 current Jobicy Role snapshot overrides expanded structured region countries'})
        facts['country_provenance']=provenance
        row.extracted_facts=facts
        row.save(update_fields=['country','role_location','locations','extracted_facts','updated_at'])
        for url in (row.url,row.target_url,row.search_url,row.canonical_url):
            if url:
                repaired_urls[str(url)]=region

    for contact in Contact.objects.filter(source_url__icontains='jobicy.com/jobs/').iterator(chunk_size=100):
        region=repaired_urls.get(str(contact.source_url or ''))
        if not region:
            continue
        item={'kind':'region','label':region,'code':region.replace(' ','_').upper(),'icon':'','source':'source_role_location','evidence':f'Remote from {region}'}
        contact.company_country=region
        contact.company_locations=[item]
        contact.save(update_fields=['company_country','company_locations'])

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.93').exists():
        AuditLog.objects.create(
            actor='system',action='version_upgraded',version='0.11.93',
            summary='ScoutBox upgraded to version 0.11.93.',metadata={'version':'0.11.93'},
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0164_v01192_followup_repairs')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
