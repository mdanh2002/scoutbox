import json
import re
from urllib.parse import urlsplit

from django.db import migrations

PUBLIC_SUFFIX_2={'co.uk','org.uk','ac.uk','com.au','net.au','org.au','co.nz','com.sg','com.my','co.jp','co.kr','ac.kr','co.in','com.br','com.cn','com.tw','edu.sg'}
THIRD_PARTY_HOSTS={
    'linkedin.com','indeed.com','glassdoor.com','github.com','gitlab.com','bitbucket.org','wellfound.com',
    'ziprecruiter.com','simplyhired.com','monster.com','seek.com','jobsdb.com','findjob24h.com','reddit.com',
}
HOST_LABELS={'linkedin','indeed','glassdoor','github','gitlab','bitbucket','wellfound','ziprecruiter','simplyhired','monster','seek','jobsdb','findjob24h','reddit','ac','snu'}
FREE_MAIL={'gmail.com','googlemail.com','outlook.com','hotmail.com','yahoo.com','icloud.com','protonmail.com','proton.me','live.com','msn.com','aol.com','gmx.com'}
BAD_EMAILS={'taops@marvell.com','help.join@vertiv.com','idisability.administrator@emerson.com'}
EMAIL_RE=re.compile(r'(?i)(?<![A-Z0-9._%+\-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![A-Z0-9._%+\-])')
NON_CONTACT_LOCAL=('privacy','gdpr','legal','compliance','security','abuse','press','media','noreply','donotreply','disability','accommodation','accommodations','accessibility')
NON_CONTACT_CONTEXT=('reasonable accommodation','request an accommodation','applicant with a disability','applicants with disabilities','accessibility assistance','accessibility support','difficulty accessing','difficulty using this website','hr helpdesk')


def _registrable(value):
    raw=str(value or '').strip().lower()
    if '@' in raw and '://' not in raw:
        raw=raw.rsplit('@',1)[-1]
    if '://' not in raw:
        raw='https://'+raw
    try:
        host=(urlsplit(raw).hostname or '').lower().removeprefix('www.')
    except Exception:
        return ''
    labels=[x for x in host.split('.') if x]
    if len(labels)<2:
        return host
    tail='.'.join(labels[-2:])
    return '.'.join(labels[-3:]) if tail in PUBLIC_SUFFIX_2 and len(labels)>=3 else tail


def _slug(value):
    return re.sub(r'[^a-z0-9]+','',str(value or '').casefold())


def _domain_company(email):
    domain=_registrable(email)
    if not domain or domain in FREE_MAIL:
        return ''
    base=domain.split('.')[0]
    return base.replace('-',' ').replace('_',' ').title()[:200]


def _host_label(company, url):
    comp=_slug(company)
    domain=_registrable(url)
    source=_slug(domain.split('.')[0] if domain else '')
    if not comp or comp in HOST_LABELS:
        return True
    if domain in THIRD_PARTY_HOSTS:
        return comp==source
    academic=domain.endswith('.edu') or '.ac.' in domain or domain.endswith('.ac.kr')
    return bool(academic and (comp==source or len(comp)<=4))


def _blocked(email, text):
    raw=str(email or '').strip().lower()
    if raw in BAD_EMAILS:
        return True
    local=raw.split('@',1)[0] if '@' in raw else raw
    compact=re.sub(r'[^a-z0-9]+','',local)
    if any(marker in compact for marker in NON_CONTACT_LOCAL):
        return True
    low=str(text or '').casefold(); pos=low.find(raw.casefold())
    if pos>=0:
        window=' '.join(low[max(0,pos-360):pos+len(raw)+360].split())
        if any(marker in window for marker in NON_CONTACT_CONTEXT):
            return True
    return False


def _explicit_company(text):
    raw=str(text or '')
    patterns=(
        r'(?im)^\s*(?:company|employer|organisation|organization|hiring company)\s*[:\-]\s*([^\r\n]{2,120})\s*$',
        r'(?im)^\s*(?:company|employer|organisation|organization|hiring company)\s*$\s*^\s*([^\r\n]{2,120})\s*$',
    )
    blocked=HOST_LABELS|{'unknown','na','none'}
    for pattern in patterns:
        m=re.search(pattern,raw)
        if not m: continue
        company=' '.join(m.group(1).split()).strip(' -–—|:')[:220]
        if company and _slug(company) not in blocked:
            return company
    return ''


def _recover(company, url, text):
    if not _host_label(company,url):
        return ''
    domain=_registrable(url)
    if not (domain in THIRD_PARTY_HOSTS or domain.endswith('.edu') or '.ac.' in domain or domain.endswith('.ac.kr')):
        return ''
    explicit=_explicit_company(text)
    if explicit:
        return explicit
    raw=str(text or '')
    for email in EMAIL_RE.findall(raw):
        email=email.strip().lower()
        if _blocked(email,raw):
            continue
        email_domain=_registrable(email)
        if not email_domain or email_domain in FREE_MAIL or email_domain==domain:
            continue
        candidate=_domain_company(email)
        candidate_slug=_slug(candidate)
        if len(candidate_slug)<5:
            continue
        scrubbed=re.sub(re.escape(email),' ',raw,flags=re.I)
        scrubbed=re.sub(re.escape(email_domain),' ',scrubbed,flags=re.I)
        normalized=_slug(scrubbed)
        if candidate_slug in normalized:
            return candidate
    return ''


def repair(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')

    for row in Opportunity.objects.only('pk','company','description','raw_search_snippet','extracted_facts','company_intel','target_url','canonical_url','url','search_url').iterator(chunk_size=200):
        url=str(row.target_url or row.canonical_url or row.url or row.search_url or '')
        try:
            structured='\n'.join((json.dumps(row.extracted_facts or {},ensure_ascii=False,default=str),json.dumps(row.company_intel or {},ensure_ascii=False,default=str)))
        except Exception:
            structured=''
        text='\n'.join((str(row.description or ''),str(row.raw_search_snippet or ''),structured))
        employer=_recover(row.company,url,text)
        if employer and employer.casefold()!=str(row.company or '').strip().casefold():
            Opportunity.objects.filter(pk=row.pk).update(company=employer[:220])

    for row in CompanyLead.objects.only('pk','company','evidence','summary','match_summary','ai_state','company_intel','target_url','source_url','search_url').iterator(chunk_size=200):
        url=str(row.target_url or row.source_url or row.search_url or '')
        try:
            structured='\n'.join((json.dumps(row.ai_state or {},ensure_ascii=False,default=str),json.dumps(row.company_intel or {},ensure_ascii=False,default=str)))
        except Exception:
            structured=''
        text='\n'.join((str(row.evidence or ''),str(row.summary or ''),str(row.match_summary or ''),structured))
        employer=_recover(row.company,url,text)
        if employer and employer.casefold()!=str(row.company or '').strip().casefold():
            CompanyLead.objects.filter(pk=row.pk).update(company=employer[:220])


class Migration(migrations.Migration):
    dependencies=[('portal','0081_v01023_contact_association_repair')]
    operations=[migrations.RunPython(repair,migrations.RunPython.noop)]
