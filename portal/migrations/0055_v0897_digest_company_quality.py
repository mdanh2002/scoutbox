import re
from urllib.parse import urlsplit
from django.db import migrations

PLATFORMS=(
    'indeed.com','glassdoor.com','linkedin.com','ziprecruiter.com','simplyhired.com','monster.com',
    'greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com',
    'facebook.com','reddit.com','x.com','twitter.com','youtube.com','github.com','gitlab.com',
)
FREE_MAIL={'gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com','icloud.com','proton.me','protonmail.com','aol.com'}
TWO_PART={'co.uk','org.uk','com.au','net.au','co.nz','com.sg','com.my','co.jp','co.in','com.br','com.mx','co.za'}
SIGNALS=[
    (r'\bedk\s*ii\b|\bedk2\b','EDK II',3),(r'\bdxe\b|\bsmm\b|\bpei\b','UEFI DXE/SMM/PEI',3),
    (r'\bsecure boot\b|\bmeasured boot\b|\btpm\b','Secure/Measured Boot',3),(r'\bbmc\b|\bipmi\b|\bredfish\b','BMC/IPMI/Redfish',3),
    (r'\bacpi\b','ACPI',3),(r'\bpcie\b|\bpci express\b','PCIe',3),(r'\bcoreboot\b','coreboot',3),(r'\bu-boot\b|\bbootloader\b','bootloader/U-Boot',3),
    (r'\bjtag\b|\bswd\b','JTAG/SWD',3),(r'\bzephyr\b','Zephyr',3),(r'\bfreertos\b|\bfree rtos\b','FreeRTOS',3),(r'\bdspic\b','dsPIC',3),
    (r'\bqemu\b.*\bkvm\b|\bkvm\b.*\bqemu\b','QEMU/KVM',3),(r'\breverse engineer(?:ing)?\b','reverse engineering',3),
    (r'\bvulnerabilit(?:y|ies) research\b|\bsecurity research\b','security research',3),(r'\bmalware analys(?:is|t)\b','malware analysis',3),
    (r'\bprotocol (?:reverse engineering|analysis)\b','protocol analysis',3),(r'\bbios\b|\buefi\b','BIOS/UEFI',3),(r'\byocto\b|\bbuildroot\b','Yocto/Buildroot',3),
    (r'\bhypervisor\b','hypervisor',2),(r'\bvirtuali[sz]ation\b','virtualization',2),(r'\bdevice drivers?\b|\bkernel drivers?\b','device drivers',2),
    (r'\bembedded linux\b','Embedded Linux',2),(r'\bkernel\b','kernel',2),(r'\bfpga\b','FPGA',2),(r'\brtos\b|\breal[- ]time operating system\b','RTOS',2),
    (r'\barm64\b|\baarch64\b','ARM/AArch64',2),(r'\bcobol\b','COBOL',2),(r'\blegacy systems?\b|\bobsolete systems?\b','legacy systems',2),(r'\bretro comput(?:ing|er)\b|\bvintage comput(?:ing|er)\b','retro computing',3),
]

def _host(url):
    try: return (urlsplit(str(url or '')).hostname or '').lower().removeprefix('www.')
    except Exception: return ''

def _reg(host):
    host=str(host or '').lower().strip('.').removeprefix('www.'); labels=[x for x in host.split('.') if x]
    if len(labels)<=2: return host
    return '.'.join(labels[-3:]) if '.'.join(labels[-2:]) in TWO_PART else '.'.join(labels[-2:])

def _bad(domain):
    return not domain or domain in FREE_MAIL or any(domain==d or domain.endswith('.'+d) for d in PLATFORMS)

def _company_key(v): return re.sub(r'[^a-z0-9]+','',str(v or '').casefold())

def _tokens(v):
    stop={'inc','llc','ltd','limited','corp','corporation','company','co','gmbh','plc','pty','group','holdings','technologies','technology','systems','solutions'}
    return [x for x in re.findall(r'[a-z0-9]+',str(v or '').casefold()) if len(x)>=3 and x not in stop]

def _matches_company(domain,company):
    stem=re.sub(r'[^a-z0-9]','',str(domain or '').split('.')[0]); toks=_tokens(company)
    return bool(stem and toks and any(t in stem or stem in t for t in toks))

def _candidate(row,intel):
    email=str(getattr(row,'contact_email',None) or getattr(row,'email','') or '').lower()
    if '@' in email:
        d=_reg(email.rsplit('@',1)[1])
        if not _bad(d) and (not _tokens(getattr(row,'company','')) or _matches_company(d,getattr(row,'company',''))): return d
    for src in (intel.get('sources') or []) if isinstance(intel,dict) else []:
        u=src.get('url') if isinstance(src,dict) else src; d=_reg(_host(u))
        if not _bad(d) and _matches_company(d,getattr(row,'company','')): return d
    for field in ('target_url','url','source_url','contact_url'):
        d=_reg(_host(getattr(row,field,'')))
        if not _bad(d) and _matches_company(d,getattr(row,'company','')): return d
    return ''

def _summary_from_intel(intel):
    if not isinstance(intel,dict): return ''
    vals=[]
    for item in intel.get('facts') or []:
        if not isinstance(item,dict): continue
        label=str(item.get('label') or '').casefold(); val=' '.join(str(item.get('value') or '').split()).strip()
        if val and label in {'what they do','products/technology','products and technology','products','technology'} and val.casefold() not in {x.casefold() for x in vals}: vals.append(val)
        if len(vals)>=2: break
    text=' '.join(vals)
    return (text[:597].rsplit(' ',1)[0]+'…') if len(text)>600 else text

def _highlight(row):
    facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
    text=' '.join(str(x or '') for x in (row.title,row.description,row.raw_search_snippet,row.recommendation_reason,row.remote_text))
    ai=facts.get('ai_job_summary') if isinstance(facts.get('ai_job_summary'),dict) else {}; cloud=facts.get('cloud_research') if isinstance(facts.get('cloud_research'),dict) else {}
    text+=' '+str(ai.get('text') or '')+' '+str(cloud.get('summary') or '')
    low=' '.join(text.split()).casefold(); found=[]
    for pat,label,level in SIGNALS:
        if re.search(pat,low,re.I) and label.casefold() not in {x[0].casefold() for x in found}: found.append((label,level))
    levels=[x[1] for x in found]
    if not (any(x>=3 for x in levels) or sum(1 for x in levels if x>=2)>=2): return ''
    traits=[x[0] for x in found if x[1]>=2][:3]
    if not traits: return ''
    focus=traits[0] if len(traits)==1 else (traits[0]+' and '+traits[1] if len(traits)==2 else ', '.join(traits[:-1])+' and '+traits[-1])
    remote=facts.get('remote_classification') if isinstance(facts.get('remote_classification'),dict) else {}; status=str(remote.get('status') or '').casefold()
    prefix='Fully remote ' if status=='fully_remote' else ('Remote ' if status=='remote' else ('Hybrid ' if status=='hybrid' else ''))
    text=(prefix+focus+' work').strip();
    if re.search(r'\bsecurity clearance\b|\bclearance required\b',low): text+=', with a clearance requirement'
    return (text[:1].upper()+text[1:].rstrip(' .')+'.')[:300]

def repopulate(apps,schema_editor):
    Opportunity=apps.get_model('portal','Opportunity'); Lead=apps.get_model('portal','CompanyLead'); Contact=apps.get_model('portal','Contact'); Cache=apps.get_model('portal','CompanyResearchCache')
    # Specific Opportunity highlights: generic legacy phrases become blank rather than filler.
    batch=[]
    for row in Opportunity.objects.all().iterator(chunk_size=300):
        row.list_highlight=_highlight(row); batch.append(row)
        if len(batch)>=300: Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=300); batch=[]
    if batch: Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=300)

    # Build reusable, trustworthy domain-age facts from rows whose stored age can be tied
    # to a company-controlled domain. This lets LinkedIn/ATS rows inherit a good age when
    # another stored record for the same company already has it.
    age_by_company={}
    for Model in (Opportunity,Lead,Contact):
        for row in Model.objects.all().iterator(chunk_size=300):
            intel=row.company_intel if isinstance(row.company_intel,dict) else {}; st=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
            if not st.get('domain_registered_at'): continue
            cand=_candidate(row,intel); stored=str(st.get('domain_age_domain') or '').lower()
            source=_reg(_host(getattr(row,'target_url','') or getattr(row,'url','') or getattr(row,'source_url','')))
            trusted=cand and ((stored and stored==cand) or (not stored and source==cand and not _bad(source)))
            if trusted:
                key=_company_key(getattr(row,'company',''))
                if key: age_by_company[key]=(cand,{k:st.get(k) for k in ('domain_registered_at','domain_age_years','domain_age_label')})

    for Model in (Opportunity,Lead,Contact):
        updates=[]
        for row in Model.objects.all().iterator(chunk_size=300):
            intel=dict(row.company_intel or {}); st=dict(intel.get('structured') or {})
            if not any(st.get(k) not in (None,'') for k in ('domain_registered_at','domain_age_years','domain_age_label','domain_age_domain')): continue
            cand=_candidate(row,intel); stored=str(st.get('domain_age_domain') or '').lower(); source=_reg(_host(getattr(row,'target_url','') or getattr(row,'url','') or getattr(row,'source_url','')))
            trusted=cand and ((stored and stored==cand) or (not stored and source==cand and not _bad(source)))
            facts=[dict(x) for x in (intel.get('facts') or []) if isinstance(x,dict) and str(x.get('label') or '').casefold()!='domain age']
            if trusted:
                st['domain_age_domain']=cand
            else:
                key=_company_key(getattr(row,'company','')); replacement=age_by_company.get(key) if key else None
                for key in ('domain_registered_at','domain_age_years','domain_age_label','domain_age_domain'): st.pop(key,None)
                if replacement:
                    domain,data=replacement; st.update(data); st['domain_age_domain']=domain
                    st.pop('domain_age_refresh_needed',None)
                else:
                    # Do not query the network from a data migration. Mark this record for
                    # one normal company-research repair pass so its real company domain can
                    # be discovered and RDAP age repopulated outside the migration transaction.
                    domain=''; st['domain_age_refresh_needed']=True
            if trusted:
                st.pop('domain_age_refresh_needed',None)
            if st.get('domain_registered_at'):
                domain=st.get('domain_age_domain') or cand
                facts.append({'label':'Domain Age','value':f"{st.get('domain_age_label') or ''} ({domain}; registered {st.get('domain_registered_at')})".strip(),'verification':'domain-registration'})
            intel['structured']=st; intel['facts']=facts[:12]; row.company_intel=intel; updates.append(row)
            if len(updates)>=300: Model.objects.bulk_update(updates,['company_intel'],batch_size=300); updates=[]
        if updates: Model.objects.bulk_update(updates,['company_intel'],batch_size=300)

    Cache.objects.filter(domain__in=list(PLATFORMS)).delete()
    for d in PLATFORMS:
        Cache.objects.filter(domain__endswith='.'+d).delete()

    # Backfill blank Address Book company summaries from already-captured company/lead evidence.
    company_summary={}; email_summary={}
    for row in Opportunity.objects.all().iterator(chunk_size=300):
        summary=_summary_from_intel(row.company_intel or {})
        if summary:
            if row.company: company_summary.setdefault(_company_key(row.company),summary)
            if row.contact_email: email_summary.setdefault(row.contact_email.strip().casefold(),summary)
    for row in Lead.objects.all().iterator(chunk_size=300):
        summary=_summary_from_intel(row.company_intel or {}) or ' '.join(str(row.summary or '').split()).strip()[:600]
        if summary:
            if row.company: company_summary.setdefault(_company_key(row.company),summary)
            if row.contact_email: email_summary.setdefault(row.contact_email.strip().casefold(),summary)
    updates=[]
    for row in Contact.objects.filter(company_summary='').iterator(chunk_size=300):
        summary=_summary_from_intel(row.company_intel or {}) or email_summary.get(str(row.email or '').strip().casefold(),'') or company_summary.get(_company_key(row.company),'')
        if summary:
            row.company_summary=summary[:2000]; updates.append(row)
            if len(updates)>=300: Contact.objects.bulk_update(updates,['company_summary'],batch_size=300); updates=[]
    if updates: Contact.objects.bulk_update(updates,['company_summary'],batch_size=300)

def noop(apps,schema_editor): pass

class Migration(migrations.Migration):
    dependencies=[('portal','0054_v0896_rephrase_opportunity_highlights')]
    operations=[migrations.RunPython(repopulate,noop)]
