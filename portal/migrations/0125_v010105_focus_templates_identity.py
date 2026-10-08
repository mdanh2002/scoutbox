from django.db import migrations, models
from django.utils import timezone
from datetime import timedelta
import re

PLATFORM_NAMES={
    'workopolis','gulftalent','jobicy','indeed','linkedin','glassdoor','jobsdb','jobstreet','himalayas','builtin','built in',
    'remoteok','we work remotely','weworkremotely','workingnomads','working nomads','ziprecruiter','monster','careerbuilder',
}

BAD_ROLE_PREFIX_RE=re.compile(r'(?is)^\s*(?:cover\s+letter\s+assistant|resume\s+assistant|cv\s+assistant)\b(?:\s+about\s+this\s+role\.?|\s+for\s+this\s+role\.?|[^A-Za-z0-9]{0,40})*\s*')
ROLE_WORD_RE=re.compile(r'(?i)\b(?:engineer|developer|architect|manager|analyst|specialist|consultant|designer|administrator|scientist|researcher|sales|devops|backend|frontend|full\s*stack|security|firmware|software|platform|cloud|qa|quality)\b')

def norm_company(value):
    text=str(value or '').casefold()
    text=re.sub(r'\b(?:inc|incorporated|llc|ltd|limited|corp|corporation|company|co|gmbh|plc|pty|pte|group|holdings)\b',' ',text)
    return re.sub(r'[^a-z0-9]+',' ',text).strip()

def platformish(value):
    key=norm_company(value)
    compact=key.replace(' ','')
    aliases={norm_company(x) for x in PLATFORM_NAMES}
    return bool(key in aliases or compact in {x.replace(' ','') for x in aliases})

def plausible_company(value):
    raw=re.sub(r'\s+',' ',str(value or '')).strip(' \t\r\n-–—|:;,')
    if not raw or len(raw)<2 or len(raw)>160 or platformish(raw): return False
    low=raw.casefold()
    if low in {'customer service','employer','employers','job search','search jobs','post a job'}: return False
    if any(x in low for x in ('employers register','register for free','products & prices','customer service','about this role','job description')): return False
    return True

def recover_employer(text):
    raw=str(text or '')
    patterns=(
        r'(?im)^\s*(?:company|employer|organisation|organization|hiring company)\s*[:\-]\s*([^\r\n]{2,120})\s*$',
        r'(?im)^\s*(?:company|employer|organisation|organization|hiring company)\s*$\s*^\s*([^\r\n]{2,120})\s*$',
        r'(?im)^\s*([A-Z][A-Za-z0-9&+.\'’()\- ]{1,80}?)\s+(?:seeks|is seeking|is hiring|is looking for|looks for|hiring)\b',
        r'(?i)\b(?:at|with)\s+([A-Z][A-Za-z0-9&+.\'’()\- ]{1,80}?)(?=[.,;]|\s+(?:seeks|is|has|to|for|in)\b)',
    )
    for pat in patterns:
        m=re.search(pat,raw)
        if m:
            company=' '.join(m.group(1).split()).strip(' -–—|:;,')[:160]
            if plausible_company(company): return company
    return ''

def clean_title(value, text=''):
    title=str(value or '')
    title=BAD_ROLE_PREFIX_RE.sub(' ', title).strip(' -–—|:;,.')
    if ROLE_WORD_RE.search(title): return title[:300]
    # Try first role-looking line from page text.
    for line in str(text or '').splitlines()[:80]:
        line=' '.join(line.split()).strip(' -–—|:;,.')
        if 4 <= len(line) <= 120 and ROLE_WORD_RE.search(line) and not re.search(r'(?i)cover\s+letter\s+assistant|salary search|popular questions|job alert',line):
            return line[:300]
    return title[:300]

def repair_upgrade_state(apps, schema_editor):
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    PortalSettings=apps.get_model('portal','PortalSettings')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    now=timezone.now()
    BackgroundJob.objects.filter(label__icontains='Rebuild Focus taxonomy for 0.10.102',status__in=['queued','running']).update(status='stopped',message='Superseded by ScoutBox 0.10.105 stable Focus lifecycle',finished_at=now)
    BackgroundJob.objects.filter(label__icontains='Focus taxonomy',status='running',created_at__lt=now-timedelta(hours=6)).update(status='stopped',message='Stale Focus rebuild superseded by ScoutBox 0.10.105',finished_at=now)
    for ps in PortalSettings.objects.all():
        ps.integrity_repair_version=''
        ps.focus_taxonomy_version='0.10.105'
        ps.save(update_fields=['integrity_repair_version','focus_taxonomy_version'])
    for model in (Opportunity, CompanyLead, Contact):
        for row in model.objects.all().iterator(chunk_size=500):
            changed=[]
            # Remove too-specific unsuitable-opportunity notes from retained leads/contacts.
            if hasattr(row,'note'):
                note=str(getattr(row,'note') or '')
                if re.search(r'(?i)previous\s+opportunity\s+#?\d+\s+was\s+unsuitable|from\s+unsuitable\s+opportunity',note):
                    setattr(row,'note','Retained as a company-level lead after the specific vacancy was not suitable.'); changed.append('note')
            if hasattr(row,'title'):
                title=str(getattr(row,'title') or '')
                if BAD_ROLE_PREFIX_RE.search(title) or re.search(r'(?i)^\s*about\s+this\s+role\.?\s*$',title):
                    new_title=clean_title(title, getattr(row,'description','') or getattr(row,'summary','') or getattr(row,'raw_search_snippet',''))
                    if new_title and new_title != title:
                        setattr(row,'title',new_title); changed.append('title')
            if hasattr(row,'company'):
                company=str(getattr(row,'company') or '')
                url=(getattr(row,'target_url','') or getattr(row,'url','') or getattr(row,'source_url','') or '')
                if platformish(company) or re.search(r'(?i)\b(?:workopolis|gulftalent|jobicy|indeed|linkedin|jobsdb|jobstreet)\b',company):
                    recovered=recover_employer('\n'.join(str(x or '') for x in (getattr(row,'description',''),getattr(row,'summary',''),getattr(row,'list_highlight',''),getattr(row,'raw_search_snippet',''))))
                    if recovered and recovered != company:
                        setattr(row,'company',recovered); changed.append('company')
                        if hasattr(row,'extracted_facts'):
                            facts=getattr(row,'extracted_facts') or {}
                            if isinstance(facts,dict):
                                facts=dict(facts); facts['company_identity_repair']={'release':'0.10.105','from':company,'to':recovered,'reason':'job-board/platform host is not employer','at':now.isoformat()}
                                setattr(row,'extracted_facts',facts); changed.append('extracted_facts')
            if changed:
                if hasattr(row,'updated_at'): changed.append('updated_at')
                try: row.save(update_fields=list(dict.fromkeys(changed)))
                except Exception: pass

class Migration(migrations.Migration):
    dependencies=[('portal','0124_v010104_focus_integrity')]
    operations=[
        migrations.AddField(
            model_name='campaigntemplate',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, help_text='When this template was moved to the Recycle Bin.', null=True),
        ),
        migrations.RunPython(repair_upgrade_state, migrations.RunPython.noop),
    ]
