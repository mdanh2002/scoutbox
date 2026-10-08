import re
from urllib.parse import urlsplit

from django.db import migrations
from django.utils import timezone


GENERIC={
    'jobs','job','careers','career','recruiting','recruitment','talent','hr','humanresources','people',
    'hello','info','contact','contacts','sales','support','help','service','customer','customerservice',
    'admin','office','team','billing','enquiries','inquiries','noreply','donotreply','applications',
    'application','apply','hiring',
}
NON_CONTACT={
    'gdpr','privacy','privacyoffice','privacypolicy','dataprotection','datarequest','privacyrequest','dpo',
    'eeo','compliance','legal','terms','abuse','security','dmca','copyright','press','media',
    'investorrelations','noreply','donotreply','mailerdaemon','disability','accommodation','accessibility',
}
REGIONS={
    'singapore','sg','apac','asia','sea','southeastasia','emea','europe','eu','uk','usa','us','canada','ca',
    'australia','au','anz','newzealand','nz','india','japan','jp','korea','kr','china','cn','hongkong','hk',
    'taiwan','tw','malaysia','my','indonesia','id','thailand','th','vietnam','vn','philippines','ph',
    'mexico','mx','brazil','br','latam','germany','de','france','fr','spain','es','italy','it',
    'netherlands','nl','sweden','se','norway','no',
}
PUBLIC_SUFFIX_2={'co.uk','org.uk','ac.uk','com.au','net.au','org.au','co.nz','com.sg','com.my','co.jp','co.kr','co.in','com.br','com.cn','com.tw'}
FREE_MAIL={'gmail.com','googlemail.com','outlook.com','hotmail.com','yahoo.com','icloud.com','protonmail.com','proton.me','live.com','msn.com','aol.com','gmx.com'}


def clean_email(value):
    raw=str(value or '').strip().lower()
    if raw.startswith('mailto:'): raw=raw[7:]
    return raw.split('?',1)[0].strip().strip("<>\"' ,;:")[:254]


def reg_domain(value):
    raw=str(value or '').strip().lower()
    if '@' in raw and '://' not in raw: raw=raw.rsplit('@',1)[-1]
    if '://' not in raw: raw='https://'+raw
    try: host=(urlsplit(raw).hostname or '').lower().removeprefix('www.')
    except Exception: return ''
    parts=[x for x in host.split('.') if x]
    if len(parts)<2: return host
    tail='.'.join(parts[-2:])
    return '.'.join(parts[-3:]) if tail in PUBLIC_SUFFIX_2 and len(parts)>=3 else tail


def company_slug(value):
    text=' '.join(str(value or '').split()).casefold()
    text=re.sub(r'\b(?:incorporated|inc|llc|ltd|limited|gmbh|ag|plc|corp|corporation|company|co|pte)\b\.?',' ',text)
    return re.sub(r'[^a-z0-9]+','',text)


def generic(email):
    local=email.split('@',1)[0].split('+',1)[0].lower()
    compact=re.sub(r'[^a-z0-9]+','',local)
    if any(x in compact for x in NON_CONTACT) or 'sales' in compact: return True
    tokens=[x for x in re.split(r'[._-]+',local) if x]
    return any(x in GENERIC for x in tokens)


def regional(email):
    local=email.split('@',1)[0].split('+',1)[0].lower()
    tokens=[re.sub(r'[^a-z0-9]+','',x) for x in re.split(r'[._-]+',local) if x]
    compact=re.sub(r'[^a-z0-9]+','',local)
    return compact in REGIONS or any(x in REGIONS and len(x)>=2 for x in tokens)


def plausible(email,company,url):
    ed=reg_domain(email)
    if not ed or ed in FREE_MAIL: return False
    sd=reg_domain(url)
    if sd and sd==ed: return True
    cs=company_slug(company)
    ds=re.sub(r'[^a-z0-9]+','',(ed.split('.')[0] if ed else ''))
    if not cs or not ds: return False
    return cs==ds or (min(len(cs),len(ds))>=5 and (cs in ds or ds in cs))


def derived_name(email):
    if generic(email): return ''
    local=email.split('@',1)[0].split('+',1)[0]
    words=[w for w in re.split(r'[._-]+',local) if w and not w.isdigit()]
    if not words or any(w.lower() in GENERIC for w in words): return ''
    return ' '.join(w.upper() if len(w)==1 else w.capitalize() for w in words[:4])[:200]


def backfill(apps, schema_editor):
    Contact=apps.get_model('portal','Contact')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    now=timezone.now()

    def add(row,source,is_lead=False):
        email=clean_email(getattr(row,'contact_email',''))
        if not email or '@' not in email: return
        if not regional(email) and generic(email): return
        url=(getattr(row,'target_url','') or getattr(row,'source_url','') or getattr(row,'canonical_url','') or getattr(row,'url','') or getattr(row,'search_url','') or '')
        company=str(getattr(row,'company','') or '').strip()
        if not plausible(email,company,url): return
        existing=Contact.objects.filter(email__iexact=email).first()
        # Recycle Bin is an explicit user tombstone: never resurrect it.
        if existing is not None: return
        name=str(getattr(row,'contact_name','') or '').strip()[:200] or derived_name(email)
        if not name and not regional(email): return
        intel=getattr(row,'company_intel',{}) if isinstance(getattr(row,'company_intel',{}),dict) else {}
        summary=(str(getattr(row,'summary','') or '')[:2000] if is_lead else '')
        Contact.objects.create(
            email=email,name=name,company=company[:200],source=source,source_url=str(url)[:1000],
            generic=False,confidence=78,company_summary=summary,company_country=str(getattr(row,'country','') or '')[:120],
            company_intel=intel,last_seen=now,is_read=False,
        )

    for row in Opportunity.objects.filter(user_deleted=False,suppressed=False).exclude(contact_email='').iterator(chunk_size=250):
        add(row,'Opportunity discovery',False)
    for row in CompanyLead.objects.filter(user_deleted=False,deleted_at__isnull=True).exclude(contact_email='').iterator(chunk_size=250):
        add(row,'Hidden Lead discovery',True)


class Migration(migrations.Migration):
    dependencies=[('portal','0079_v0954_hidden_lead_filter_job_kind')]
    operations=[migrations.RunPython(backfill,migrations.RunPython.noop)]
