import re

from django.db import migrations


NOISE = (
    r'skip generic cold-outreach lead discovery',
    r'(?:is\s+)?not a project lead target',
    r'(?:is\s+)?not an opportunity source',
    r'(?:is\s+)?not a commercial Market Studies lead',
    r'(?:is\s+)?not as (?:the )?Hidden Lead company',
    r'(?:is\s+)?not a specialist project lead',
    r'(?:but\s+)?are not lead targets',
    r'never an opportunity source',
    r'(?:is\s+)?not job listings',
    r'use as evidence',
    r'are too noisy for opportunity discovery',
    r'advertised roles can still appear under Opportunities',
    r'(?:is\s+)?not (?:a |the )?(?:direct )?Hidden Lead(?: company)? target',
    r'suppress as a generic Hidden Lead target',
    r'Added from (?:Hidden Leads?|Opportunities|Recycle Bin)',
)


def clean_reason(value):
    text=' '.join(str(value or '').split()).strip()
    for phrase in NOISE:
        text=re.sub(r'(?i)(?:^|(?<=[.;,:]))\s*'+phrase+r'\s*(?:[.;,:]|$)', ' ', text)
        text=re.sub(r'(?i)\b'+phrase+r'\b', ' ', text)
    text=re.sub(r'\s+([,.;:])',r'\1',text)
    text=re.sub(r'([,.;:])(?:\s*[,.;:])+',r'\1',text)
    text=re.sub(r'\s+',' ',text).strip(' ,;:')
    if text and text[-1] not in '.!?':
        text+='.'
    return text


def forwards(apps, schema_editor):
    SourceBlacklist=apps.get_model('portal','SourceBlacklist')
    AuditLog=apps.get_model('portal','AuditLog')
    for row in SourceBlacklist.objects.all().only('pk','reason').iterator(chunk_size=500):
        cleaned=clean_reason(row.reason)
        if cleaned != row.reason:
            SourceBlacklist.objects.filter(pk=row.pk).update(reason=cleaned)
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.90').exists():
        AuditLog.objects.create(
            actor='system', action='version_upgraded', version='0.11.90',
            summary='ScoutBox upgraded to version 0.11.90.',
            metadata={'version':'0.11.90'},
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0161_v01189_consistency_repairs')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
