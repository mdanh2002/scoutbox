import re
from urllib.parse import urlsplit

from django.db import migrations


EMAIL_RE = re.compile(r'(?<![A-Z0-9._%+\-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![A-Z0-9._%+\-])', re.I)
URL_RE = re.compile(r'https?://[^\s<>()\[\]{}\"\']+', re.I)
PREFIX = 'Cloud outreach path:'


def _url_key(url):
    raw = str(url or '').strip().rstrip('.,;:!?)]}')
    if not raw.startswith(('http://', 'https://')):
        return ''
    try:
        p = urlsplit(raw)
        host = p.netloc.lower().removeprefix('www.')
        path = re.sub(r'/+', '/', p.path or '/').rstrip('/') or '/'
        return f'{host}{path}'.casefold()
    except Exception:
        return raw.rstrip('/').casefold()


def _compact_generated_note(text, lead_url):
    text = str(text or '').strip()
    emails = []
    for raw in EMAIL_RE.findall(text):
        email = raw.strip('.,;:<>[]()').lower()
        if email and email not in emails:
            emails.append(email)
    lead_key = _url_key(lead_url)
    urls = []
    for raw in URL_RE.findall(text):
        url = raw.strip().rstrip('.,;:!?)]}')
        key = _url_key(url)
        if key and key != lead_key and key not in {_url_key(x) for x in urls}:
            urls.append(url)
    parts = []
    if emails:
        parts.append('Email: ' + ', '.join(emails[:3]))
    for url in urls[:2]:
        label = 'Contact form' if ('contact' in url.casefold() or 'contact form' in text.casefold()) else 'Contact link'
        parts.append(f'{label}: {url}')
    return ' · '.join(parts)[:1400]


def clean_cloud_outreach_notes(apps, schema_editor):
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    for lead in CompanyLead.objects.exclude(note='').iterator():
        note = str(lead.note or '')
        if PREFIX not in note:
            continue
        output = []
        changed = False
        for line in note.splitlines():
            stripped = line.strip()
            if stripped.startswith(PREFIX):
                changed = True
                generated = stripped[len(PREFIX):].strip()
                compact = _compact_generated_note(generated, lead.target_url or lead.source_url or '')
                if compact and compact.casefold() not in {x.casefold() for x in output}:
                    output.append(compact)
            else:
                output.append(line)
        if changed:
            cleaned = '\n'.join(x for x in output if str(x).strip()).strip()
            if cleaned != note:
                lead.note = cleaned
                lead.save(update_fields=['note'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0047_v0881_reliability_company_info')]

    operations = [migrations.RunPython(clean_cloud_outreach_notes, migrations.RunPython.noop)]
