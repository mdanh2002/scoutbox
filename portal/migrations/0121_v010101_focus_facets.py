import re
from collections import defaultdict

from django.db import migrations, models


FOCUS_RULES = (
    ('Embedded / Firmware', ('embedded','firmware','microcontroller','mcu','pic32','pic24','stm32','esp32','arm cortex','rtos','freertos','zephyr','bare metal','bios','uefi','bootloader','jtag','uart','spi','i2c','can bus','fpga firmware')),
    ('Virtualization / Emulation', ('qemu','virtualization','virtualisation','hypervisor','vmware','kvm','xen','emulator','emulation','virtual machine','vmm','proxmox','virtualbox')),
    ('Retro / Legacy Systems', ('ms-dos','msdos','dosbox','retro computing','legacy system','legacy systems','x86 real mode','16-bit','16 bit','8086','286','386','vintage computer','legacy peripheral')),
    ('Technical Writing', ('technical writer','technical writing','documentation engineer','documentation writer','developer education','developer educator','docs engineer','api documentation','tutorial writer','technical content','blog writer','content engineer')),
    ('Security / Reverse Engineering', ('reverse engineering','reverse engineer','security research','security researcher','vulnerability','malware','exploit','threat research','binary analysis','disassembly','forensics','red team','penetration test','application security','product security','detection engineer','abuse research','fraud research','security engineer')),
    ('Drivers / Protocols', ('device driver','device drivers','kernel driver','driver development','protocol reverse','network protocol','usb protocol','bluetooth protocol','modbus','bacnet','canopen','ethercat','pcie','pci express','hardware interface','protocol engineer','kernel module')),
    ('Infrastructure / Platform', ('devops','site reliability','sre','platform engineer','infrastructure engineer','kubernetes','docker','ci/cd','continuous integration','cloud infrastructure','systems engineer','linux systems','network infrastructure','release engineer','build engineer','developer infrastructure')),
    ('AI / Data', ('machine learning','artificial intelligence','generative ai','gen ai','llm','large language model','data scientist','data science','data engineer','ml engineer','ai engineer','computer vision','nlp','pytorch','tensorflow','rag','agentic','data analyst','analytics engineer')),
    ('Hardware / Electronics', ('hardware engineer','electronics engineer','electrical engineer','pcb','schematic','board design','signal integrity','rf engineer','silicon','asic','fpga','soc design','electronics','hardware development','validation engineer')),
    ('Customer Engineering / Support', ('customer success engineer','support engineer','technical support','solutions engineer','solution engineer','field application engineer','field applications engineer','sales engineer','implementation engineer','professional services engineer','customer engineer','support specialist','product support')),
    ('Sales / Growth', ('sales development','business development','account executive','sales representative','gtm engineer','go-to-market','growth engineer','growth marketing','sales operations','revenue operations','presales','pre-sales','partnerships')),
    ('Developer Tools / Systems', ('compiler','debugger','developer tools','developer tooling','systems software','system software','kernel','runtime','toolchain','build system','low level','low-level','c++','rust','golang','backend engineer','software engineer','software developer','systems programming','distributed systems')),
)


def _flatten(value):
    if isinstance(value,dict):
        out=[]
        for key in ('title','summary','description','role','technologies','skills','keywords','company','industry','fit_reason'):
            raw=value.get(key)
            if isinstance(raw,(str,int,float)): out.append(str(raw))
            elif isinstance(raw,list): out.extend(str(x) for x in raw[:30] if isinstance(x,(str,int,float)))
        return ' '.join(out)
    return str(value or '')


def _classify(text, campaign=''):
    hay=' '+re.sub(r'\s+',' ',str(text or '').casefold())+' '
    hint=' '+re.sub(r'\s+',' ',str(campaign or '').casefold())+' '
    scores=defaultdict(float)
    for name, phrases in FOCUS_RULES:
        for phrase in phrases:
            p=phrase.casefold()
            if p in hay: scores[name]+=2.2 if (' ' in p or '-' in p or '/' in p) else 1.0
            if p in hint: scores[name]+=0.7 if ' ' in p else 0.35
    if not scores: return 'Unclassified'
    name=max(scores,key=scores.get)
    return name if scores[name] >= 1.0 else 'Unclassified'


def backfill_all_existing_focus(apps, schema_editor):
    """One-time full backfill: every existing row is classified without the runtime sample limit."""
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    Campaign=apps.get_model('portal','Campaign')
    campaign_names=dict(Campaign.objects.values_list('pk','name'))

    # Deliberately iterate the entire existing inventory.  The configurable comparison
    # depth applies only to records created after this upgrade, not this one-time backfill.
    for row in Opportunity.objects.all().iterator(chunk_size=500):
        text=' '.join((str(row.title or ''),str(row.company or ''),str(row.list_highlight or ''),str(row.description or ''),str(row.role_location or ''),_flatten(row.extracted_facts or {})))
        focus=_classify(text,campaign_names.get(row.origin_campaign_id,''))
        Opportunity.objects.filter(pk=row.pk).update(focus=focus)
    for row in CompanyLead.objects.all().iterator(chunk_size=500):
        text=' '.join((str(row.company or ''),str(row.summary or ''),str(row.match_summary or ''),str(row.evidence or ''),str(row.contact_name or ''),_flatten(row.company_intel or {})))
        focus=_classify(text,campaign_names.get(row.origin_campaign_id,''))
        CompanyLead.objects.filter(pk=row.pk).update(focus=focus)
    for row in Contact.objects.all().iterator(chunk_size=500):
        text=' '.join((str(row.company or ''),str(row.title or ''),str(row.company_summary or ''),str(row.name or ''),str(row.email or ''),str(row.notes or ''),_flatten(row.company_intel or {})))
        focus=_classify(text,'')
        Contact.objects.filter(pk=row.pk).update(focus=focus)



class Migration(migrations.Migration):
    dependencies=[('portal','0120_v010100_company_domain_evidence_reuse')]
    operations=[
        migrations.AddField(model_name='portalsettings',name='focus_comparison_records',field=models.PositiveSmallIntegerField(default=100,help_text='Target same-list comparison depth for Focus assignment. UI clamp: 25-500.')),
        migrations.AddField(model_name='portalsettings',name='max_focus_groups',field=models.PositiveSmallIntegerField(default=15,help_text='Target maximum active Focus groups. UI clamp: 5-30.')),
        migrations.AddField(model_name='opportunity',name='focus',field=models.CharField(blank=True,db_index=True,default='',help_text='Content-based Focus classification, independent from Campaign provenance.',max_length=80)),
        migrations.AddField(model_name='companylead',name='focus',field=models.CharField(blank=True,db_index=True,default='',help_text='Content-based Focus classification, independent from Campaign provenance.',max_length=80)),
        migrations.AddField(model_name='contact',name='focus',field=models.CharField(blank=True,db_index=True,default='',help_text='Content-based Focus classification for Address Book filtering.',max_length=80)),
        migrations.RunPython(backfill_all_existing_focus,migrations.RunPython.noop),
    ]
