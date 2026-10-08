import re
from django.db import migrations


SECTION_RE = re.compile(
    r'\[(PAGE_TITLE|CURRENT_JOB_HEADER|JOB_DESCRIPTION|RESPONSIBILITIES|QUALIFICATIONS|BENEFITS|COMPENSATION|APPLICATION|COMPANY_PROFILE|RELATED_JOBS|FOOTER|NAVIGATION|SOURCE_URL|TITLE|TEXT)\]',
    re.I,
)
PREFIX_RE = re.compile(r'^\s*\[[A-Z][A-Z0-9_ -]{2,40}\]\s*')


def clean_hidden_lead_summaries(apps, schema_editor):
    """Remove extraction labels from existing summaries without discarding their prose."""
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    for lead in CompanyLead.objects.all().only('pk', 'summary').iterator(chunk_size=500):
        original = str(lead.summary or '')
        if not original:
            continue
        if original.strip().casefold() == 'summary pending.':
            cleaned = ''
        elif SECTION_RE.search(original) or PREFIX_RE.search(original):
            cleaned = SECTION_RE.sub(' ', original)
            cleaned = PREFIX_RE.sub('', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' \t\r\n-–—|·:;')[:1600]
        else:
            continue
        if cleaned != original:
            CompanyLead.objects.filter(pk=lead.pk).update(summary=cleaned)


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0149_v01126_canonical_hidden_lead_reassessment'),
    ]

    operations = [
        migrations.RunPython(clean_hidden_lead_summaries, migrations.RunPython.noop),
    ]
