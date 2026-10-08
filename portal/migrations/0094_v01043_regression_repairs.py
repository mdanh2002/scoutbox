import re
from django.db import migrations
from django.utils import timezone

FOREIGN=re.compile(r'[\u1100-\u11ff\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\u0400-\u052f\u0600-\u06ff\u0750-\u077f\u0e00-\u0e7f\u1780-\u17ff]+')
LATIN=re.compile(r'[A-Za-z]{2,}')
ADULT=[
    re.compile(r'\b(?:porn|pornographic|xxx|hardcore|explicit sex|sex video|adult video|adult content|nude(?:s| photos?| videos?)?|camgirl|webcam sex)\b',re.I),
    re.compile(r'\b(?:escort service|escorts?|sexual services?|hookup sex|casual sex|live sex|sex chat)\b',re.I),
    re.compile(r'\b(?:blowjob|handjob|anal sex|oral sex|gangbang|cumshot|masturbat(?:e|ion|ing))\b',re.I),
]

def clean_title(value):
    text=' '.join(str(value or '').split()).strip()
    if not text: return ''
    if FOREIGN.search(text) and not LATIN.search(text): return ''
    if FOREIGN.search(text):
        text=FOREIGN.sub(' ',text)
        text=re.sub(r'\s+(?:[-–—|·:/]\s*){2,}',' - ',text)
        text=re.sub(r'\s*[-–—|·:/]\s*$','',text)
        text=re.sub(r'^\s*[-–—|·:/]\s*','',text)
        text=re.sub(r'\s{2,}',' ',text).strip(' -–—|·:;/,')
    return text

def forwards(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    for row in Opportunity.objects.filter(user_deleted=False).only('pk','title').iterator(chunk_size=500):
        cleaned=clean_title(row.title)
        if cleaned!=str(row.title or ''):
            # Keep an explicit safe fallback rather than a foreign search-shell fragment.
            row.title=cleaned or 'Opportunity'
            row.save(update_fields=['title'])
    # Historical high-confidence adult Hidden Leads are recycled. This pass intentionally
    # uses only explicit language to avoid false positives on ordinary company content.
    now=timezone.now()
    for row in CompanyLead.objects.filter(user_deleted=False).only('pk','company','summary','match_summary','evidence','target_url','source_url').iterator(chunk_size=500):
        blob=' '.join(str(x or '') for x in (row.company,row.summary,row.match_summary,row.evidence,row.target_url,row.source_url))[:30000]
        if any(p.search(blob) for p in ADULT):
            row.user_deleted=True
            if hasattr(row,'deleted_at'): row.deleted_at=now
            fields=['user_deleted']+(['deleted_at'] if hasattr(row,'deleted_at') else [])
            row.save(update_fields=fields)
    # Job-presence warnings are invalid for company/contact pages. Force a fresh semantic
    # health result instead of retaining legacy CONTENT_NOT_JOB state.
    CompanyLead.objects.filter(target_check_error__startswith='CONTENT_NOT_JOB:').update(target_check_error='')
    Contact.objects.filter(domain_check_error__startswith='CONTENT_NOT_JOB:').update(domain_check_error='')

def backwards(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies=[('portal','0093_v01042_quality_filters_health')]
    operations=[migrations.RunPython(forwards,backwards)]
