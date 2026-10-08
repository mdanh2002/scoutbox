import re
from django.db import migrations

SIGNALS=[
    (r'\bedk\s*ii\b|\bedk2\b','EDK II',3,'firmware'),(r'\bdxe\b|\bsmm\b|\bpei\b','UEFI DXE/SMM/PEI',3,'firmware'),
    (r'\bsecure boot\b|\bmeasured boot\b|\btpm\b','Secure/Measured Boot',3,'security'),(r'\bbmc\b|\bipmi\b|\bredfish\b','BMC/IPMI/Redfish',3,'firmware'),
    (r'\bacpi\b','ACPI',3,'firmware'),(r'\bpcie\b|\bpci express\b','PCIe',3,'firmware'),(r'\bcoreboot\b','coreboot',3,'firmware'),
    (r'\bu-boot\b|\bbootloader\b','U-Boot/bootloader',3,'firmware'),(r'\bjtag\b|\bswd\b','JTAG/SWD',3,'reverse'),
    (r'\bghidra\b|\bida pro\b|\bida\b','Ghidra/IDA',3,'reverse'),(r'\bbinary analys(?:is|t)\b','binary analysis',3,'reverse'),
    (r'\bfuzz(?:ing|er)\b','fuzzing',3,'security'),(r'\bzephyr\b','Zephyr',3,'embedded'),(r'\bfreertos\b|\bfree rtos\b','FreeRTOS',3,'embedded'),
    (r'\bdspic\b','dsPIC',3,'embedded'),(r'\bqemu\b.*\bkvm\b|\bkvm\b.*\bqemu\b','QEMU/KVM',3,'virtualization'),(r'\bqemu\b','QEMU',3,'virtualization'),
    (r'\breverse engineer(?:ing|er)?\b','reverse engineering',3,'reverse'),(r'\bvulnerabilit(?:y|ies) research(?:er)?\b|\bsecurity research(?:er)?\b','security research',3,'security'),
    (r'\bmalware analys(?:is|t)\b','malware analysis',3,'reverse'),(r'\bprotocol (?:reverse engineering|analysis)\b','protocol analysis',3,'reverse'),
    (r'\bbios\b|\buefi\b','BIOS/UEFI',3,'firmware'),(r'\byocto\b|\bbuildroot\b','Yocto/Buildroot',3,'embedded'),(r'\bautosar\b','AUTOSAR',3,'embedded'),
    (r'\brisc[- ]?v\b','RISC-V',3,'embedded'),(r'\bhypervisor\b','hypervisor',2,'virtualization'),(r'\bkvm\b','KVM',2,'virtualization'),
    (r'\bvirtuali[sz]ation\b','virtualization',2,'virtualization'),(r'\bdevice drivers?\b|\bkernel drivers?\b','device drivers',2,'kernel'),
    (r'\bembedded linux\b','Embedded Linux',2,'embedded'),(r'\blinux kernel\b|\bkernel space\b|\bkernel-space\b','Linux kernel',2,'kernel'),
    (r'\bfpga\b','FPGA',2,'embedded'),(r'\brtos\b|\breal[- ]time operating system\b','RTOS',2,'embedded'),(r'\barm64\b|\baarch64\b','ARM/AArch64',2,'embedded'),
    (r'\bx86(?:-64)?\b|\bx64\b','x86/x64',2,'firmware'),(r'\bmicrocontrollers?\b|\bmcu\b','microcontrollers',2,'embedded'),
    (r'\btechnical writ(?:er|ing)\b|\btechnical documentation\b','technical writing',2,'writing'),(r'\bapi documentation\b|\bdeveloper documentation\b|\bdocs-as-code\b','developer/API docs',2,'writing'),
    (r'\bdeveloper relations\b|\bdeveloper advocate\b|\bdevrel\b','developer relations',2,'devrel'),(r'\bcobol\b','COBOL',2,'legacy'),
    (r'\blegacy systems?\b|\bobsolete systems?\b','legacy systems',2,'legacy'),(r'\bretro comput(?:ing|er)\b|\bvintage comput(?:ing|er)\b','retro computing',3,'legacy'),
    (r'\bfirmware\b','firmware',1,'firmware'),(r'\bembedded systems?\b|\bembedded software\b|\bembedded engineer\b','embedded systems',1,'embedded'),
    (r'\barm\b','ARM',1,'embedded'),(r'\bc\s*/\s*c\+\+|c\+\+','C/C++',1,'kernel'),(r'\brust\b','Rust',1,'kernel'),
]

def _signals(text):
    low=' '.join(str(text or '').split()).casefold(); out=[]; seen=set()
    for order,(pat,label,level,interest) in enumerate(SIGNALS):
        if re.search(pat,low,re.I) and label.casefold() not in seen:
            seen.add(label.casefold()); out.append({'label':label,'level':level,'interest':interest,'order':order})
    return out

def _enough(rows):
    levels=[x['level'] for x in rows]
    return any(x>=2 for x in levels) or sum(1 for x in levels if x==1)>=2

def _interest(rows):
    s={x['interest'] for x in rows}
    if 'devrel' in s: return 'developer-relations/domain fit'
    if 'writing' in s: return 'technical-writing/domain fit'
    if 'firmware' in s and 'security' in s: return 'firmware/security fit'
    if 'reverse' in s and 'security' in s: return 'reversing/security fit'
    if 'security' in s: return 'security-research fit'
    if 'virtualization' in s: return 'virtualization fit'
    if 'reverse' in s: return 'reverse-engineering fit'
    if 'firmware' in s and 'embedded' in s: return 'embedded firmware fit'
    if 'firmware' in s: return 'firmware/low-level fit'
    if 'kernel' in s and 'embedded' in s: return 'low-level embedded fit'
    if 'kernel' in s: return 'kernel/low-level fit'
    if 'embedded' in s: return 'embedded/RTOS fit'
    if 'legacy' in s: return 'legacy/retro fit'
    return 'specialist fit'

def _highlight(row):
    facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
    ai=facts.get('ai_job_summary') if isinstance(facts.get('ai_job_summary'),dict) else {}
    cloud=facts.get('cloud_research') if isinstance(facts.get('cloud_research'),dict) else {}
    trusted=' '.join(str(x or '') for x in (row.title,row.description,ai.get('text'),cloud.get('summary')))
    rows=_signals(trusted)
    title_rows=_signals(row.title)
    if not _enough(rows) and title_rows and row.raw_search_snippet:
        rows=_signals(str(row.title or '')+' '+str(row.raw_search_snippet or ''))
    if not _enough(rows): return ''
    ranked=sorted(rows,key=lambda x:(-x['level'],x['order'])); chosen=[]
    for item in ranked:
        low=item['label'].casefold()
        if any(low in x['label'].casefold() or x['label'].casefold() in low for x in chosen): continue
        chosen.append(item)
        if len(chosen)>=2: break
    return (' + '.join(x['label'] for x in chosen)+' — '+_interest(rows))[:300]

def repopulate(apps,schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    batch=[]
    for row in Opportunity.objects.all().iterator(chunk_size=300):
        row.list_highlight=_highlight(row); batch.append(row)
        if len(batch)>=300:
            Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=300); batch=[]
    if batch: Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=300)

def noop(apps,schema_editor): pass

class Migration(migrations.Migration):
    dependencies=[('portal','0055_v0897_digest_company_quality')]
    operations=[migrations.RunPython(repopulate,noop)]
