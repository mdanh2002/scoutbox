import re
from django.db import migrations

SIGNALS=[
    (r'\bdspic\b','dsPIC'),(r'\bqemu\b.*\bkvm\b|\bkvm\b.*\bqemu\b','QEMU/KVM'),
    (r'\breverse engineer(?:ing)?\b','reverse engineering'),
    (r'\bvulnerabilit(?:y|ies) research\b|\bsecurity research\b','security research'),
    (r'\bmalware analys(?:is|t)\b','malware analysis'),(r'\barm64\b|\baarch64\b','ARM/AArch64'),
    (r'\barm\b','ARM'),(r'\bfirmware\b','firmware'),(r'\bmicrocontrollers?\b|\bmcu\b','microcontrollers'),
    (r'\brtos\b|\breal[- ]time operating system\b','RTOS'),(r'\bfpga\b','FPGA'),(r'\bkernel\b','kernel'),
    (r'\bhypervisor\b','hypervisor'),(r'\bvirtuali[sz]ation\b','virtualization'),(r'\bbios\b|\buefi\b','BIOS/UEFI'),
    (r'\byocto\b|\bbuildroot\b','Yocto/Buildroot'),(r'\bprotocol (?:reverse engineering|analysis)\b','protocol analysis'),
    (r'\bc\s*/\s*c\+\+\b|\bc\+\+\b','C/C++'),(r'\brust\b','Rust'),(r'\bcobol\b','COBOL'),
    (r'\blegacy systems?\b|\bobsolete systems?\b','legacy systems'),
    (r'\bretro comput(?:ing|er)\b|\bvintage comput(?:ing|er)\b','retro computing'),
]

def _join(items):
    if not items: return ''
    if len(items)==1: return items[0]
    if len(items)==2: return f'{items[0]} and {items[1]}'
    return ', '.join(items[:-1])+f' and {items[-1]}'

def _phrase(signals):
    arrangements=[]; travel=[]; traits=[]
    for item in signals:
        low=item.casefold()
        if low in {'fully remote','remote','hybrid','part-time','contract'}: arrangements.append(item)
        elif 'travel' in low or 'clearance' in low: travel.append(item)
        else: traits.append(item)
    lead=''
    if arrangements:
        primary=arrangements[0]
        if primary.casefold() in {'fully remote','remote','hybrid'}: lead=f'{primary} role'
        elif primary.casefold()=='contract': lead='Contract role'
        elif primary.casefold()=='part-time': lead='Part-time role'
    if traits:
        focus=_join(traits[:3])
        text=f'{lead} focused on {focus}' if lead else f'Interesting for its {focus} work'
    else:
        text=lead or 'Worth a closer look'
    if travel:
        t=travel[0].casefold()
        if t=='occasional travel': text+=', with occasional travel'
        elif t=='travel required': text+=', with travel required'
        elif 'clearance' in t: text+=', with a clearance requirement'
    return (text.rstrip(' .')+'.')[:300]

def _highlight(row):
    facts=row.extracted_facts or {}
    signals=[]
    def add(v):
        if v and v.casefold() not in {x.casefold() for x in signals}: signals.append(v)
    remote=facts.get('remote_classification') if isinstance(facts,dict) and isinstance(facts.get('remote_classification'),dict) else {}
    status=str(remote.get('status') or '').casefold()
    if status=='fully_remote': add('Fully remote')
    elif status=='remote': add('Remote')
    elif status=='hybrid': add('Hybrid')
    text=' '.join(str(x or '') for x in [row.title,row.description,row.raw_search_snippet,row.recommendation_reason,row.remote_text])
    if isinstance(facts,dict):
        ai=facts.get('ai_job_summary') if isinstance(facts.get('ai_job_summary'),dict) else {}
        cloud=facts.get('cloud_research') if isinstance(facts.get('cloud_research'),dict) else {}
        text+=' '+str(ai.get('text') or '')+' '+str(cloud.get('summary') or '')
    low=' '.join(text.split()).casefold()
    if re.search(r'\boccasional(?:ly)?\s+(?:on[- ]?site\s+)?travel\b|\btravel\s+(?:up to\s+)?(?:[1-9]\d?%|occasionally|occasionally required)\b',low): add('Occasional travel')
    elif re.search(r'\btravel (?:is )?required\b|\brequires? travel\b',low): add('Travel required')
    if re.search(r'\bpart[- ]time\b',low): add('Part-time')
    if re.search(r'\bcontract(?:or)?\b|\bfreelance\b',low): add('Contract')
    if re.search(r'\bsecurity clearance\b|\bclearance required\b',low): add('Clearance required')
    for pat,label in SIGNALS:
        if re.search(pat,low,re.I): add(label)
        if len(signals)>=5: break
    return _phrase(signals[:5])

def rephrase_all(apps,schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    batch=[]
    for row in Opportunity.objects.all().iterator(chunk_size=300):
        row.list_highlight=_highlight(row)
        batch.append(row)
        if len(batch)>=300:
            Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=300); batch=[]
    if batch: Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=300)

def noop(apps,schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies=[('portal','0053_v0895_opportunity_highlight')]
    operations=[migrations.RunPython(rephrase_all,noop)]
