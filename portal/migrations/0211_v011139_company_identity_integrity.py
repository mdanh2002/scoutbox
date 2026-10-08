import re
from urllib.parse import urlsplit
from django.db import migrations

_BAD_EXACT={
    'what we','what we are','what we do','what we offer',"what we're","what we're looking for",
    'who we are','who we','what you','who you are','we are','we have','about us','about the company',
    'the role','the company','the position','your role','our team','our company',
}

def _bad_company(value):
    raw=' '.join(str(value or '').split()).strip(' \t\r\n-–—|:;,')
    if not raw:
        return True
    low=raw.casefold()
    if low in _BAD_EXACT or any(low.startswith(x+' ') for x in _BAD_EXACT):
        return True
    if re.search(r'(?i)^(?:what|who|why|how)\s+(?:we|you|our)\b',raw):
        return True
    if re.search(r'(?i)^(?:we|you|our|the)\s+(?:are|have|offer|believe|provide|build|look|looking|seek|seeking)\b',raw):
        return True
    if re.search(r'[.!?]\s+(?:we|you|our|the)\s+(?:are|have|offer|provide|build|seek|look)\b',raw,re.I):
        return True
    return False


def _ats_company(url):
    try:
        p=urlsplit(str(url or '').strip()); host=(p.hostname or '').lower(); seg=[x for x in p.path.split('/') if x]
    except Exception:
        return ''
    token=''
    if 'greenhouse.io' in host and seg:
        token=seg[0]
    elif (host in {'jobs.lever.co','jobs.eu.lever.co'} or host.endswith('.jobs.lever.co')) and seg:
        token=seg[0]
    elif (host=='jobs.ashbyhq.com' or host.endswith('.jobs.ashbyhq.com')) and seg:
        token=seg[0]
    elif 'smartrecruiters.com' in host and seg:
        token=seg[0]
    if not token or not re.fullmatch(r'[A-Za-z0-9._-]{2,120}',token):
        return ''
    text=re.sub(r'[_-]+',' ',token).strip()
    return (text.title() if text.islower() or text.isupper() else text)[:160]


def _repair_state(state):
    state=dict(state or {}) if isinstance(state,dict) else {}
    for key in ('company','company_research','company_info'):
        state.pop(key,None)
    return state


def forwards(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    AuditLog=apps.get_model('portal','AuditLog')
    repaired_opps=0; repaired_leads=0

    for row in Opportunity.objects.all().iterator(chunk_size=250):
        if not _bad_company(row.company):
            continue
        repaired=''
        source_url=''
        for raw in (row.target_url,row.url,row.search_url):
            repaired=_ats_company(raw)
            if repaired:
                source_url=str(raw or ''); break
        if not repaired or repaired.casefold()==str(row.company or '').strip().casefold():
            continue
        old=str(row.company or '')
        facts=dict(row.extracted_facts or {}) if isinstance(row.extracted_facts,dict) else {}
        facts['company_identity']={
            'name':repaired,'source':'ats_board_repair','confidence':96,'authoritative':True,
            'reason':'0.11.139 repaired a malformed prose/heading employer using the first-party ATS board identity.',
        }
        history=list(facts.get('company_identity_repair_history') or [])
        history.append({'from':old,'to':repaired,'source_url':source_url,'release':'0.11.139'})
        facts['company_identity_repair_history']=history[-8:]
        row.company=repaired
        row.company_intel={}
        row.ai_state=_repair_state(row.ai_state)
        row.extracted_facts=facts
        row.save(update_fields=['company','company_intel','ai_state','extracted_facts','updated_at'])
        repaired_opps+=1

    for row in CompanyLead.objects.all().iterator(chunk_size=250):
        if not _bad_company(row.company):
            continue
        repaired=''
        for raw in (row.target_url,row.source_url,row.search_url):
            repaired=_ats_company(raw)
            if repaired: break
        if not repaired or repaired.casefold()==str(row.company or '').strip().casefold():
            continue
        row.company=repaired
        row.company_intel={}
        row.ai_state=_repair_state(row.ai_state)
        row.save(update_fields=['company','company_intel','ai_state','updated_at'])
        repaired_leads+=1

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.139').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.139',summary='ScoutBox upgraded to version 0.11.139.',
            metadata={
                'release':'0.11.139','company_identity_integrity':True,
                'ats_employer_repair':True,'opportunities_repaired':repaired_opps,'hidden_leads_repaired':repaired_leads,
                'detail_view_cleanup':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0210_v011138_searchapi_credential_reliability')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
