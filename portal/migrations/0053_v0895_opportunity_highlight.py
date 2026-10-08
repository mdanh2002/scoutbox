import re
from django.db import migrations, models

SIGNALS=[
    (r'\bdspic\b','dsPIC'),(r'\bqemu\b.*\bkvm\b|\bkvm\b.*\bqemu\b','QEMU/KVM'),
    (r'\breverse engineer(?:ing)?\b','Reverse engineering'),
    (r'\bvulnerabilit(?:y|ies) research\b|\bsecurity research\b','Security research'),
    (r'\barm64\b|\baarch64\b','ARM/AArch64'),(r'\bfirmware\b','Firmware'),
    (r'\bmicrocontrollers?\b|\bmcu\b','Microcontrollers'),(r'\brtos\b','RTOS'),
    (r'\bfpga\b','FPGA'),(r'\bkernel\b','Kernel'),(r'\bhypervisor\b','Hypervisor'),
    (r'\bvirtuali[sz]ation\b','Virtualization'),(r'\bbios\b|\buefi\b','BIOS/UEFI'),
    (r'\byocto\b|\bbuildroot\b','Yocto/Buildroot'),(r'\bc\s*/\s*c\+\+\b|\bc\+\+\b','C/C++'),
    (r'\brust\b','Rust'),(r'\bcobol\b','COBOL'),
    (r'\blegacy systems?\b|\bobsolete systems?\b','Legacy systems'),
    (r'\bretro comput(?:ing|er)\b|\bvintage comput(?:ing|er)\b','Retro computing'),
]

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
    if re.search(r'\boccasional(?:ly)?\s+(?:on[- ]?site\s+)?travel\b|\btravel\s+(?:up to\s+)?(?:[1-9]\d?%|occasionally)\b',low): add('Occasional travel')
    elif re.search(r'\btravel (?:is )?required\b|\brequires? travel\b',low): add('Travel required')
    if re.search(r'\bpart[- ]time\b',low): add('Part-time')
    if re.search(r'\bcontract(?:or)?\b|\bfreelance\b',low): add('Contract')
    for pat,label in SIGNALS:
        if re.search(pat,low,re.I): add(label)
        if len(signals)>=4: break
    return (' · '.join(signals[:4]) or 'Needs review')[:300]

def backfill(apps,schema_editor):
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
    dependencies=[('portal','0052_v0887_consolidated')]
    operations=[
        migrations.AddField(model_name='opportunity',name='list_highlight',field=models.CharField(blank=True,default='',help_text='Short role-specific list highlight explaining what makes this opportunity distinctive.',max_length=300)),
        migrations.RunPython(backfill,noop),
    ]
