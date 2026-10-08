from django.db import migrations, models
import re

EMAIL_RE = re.compile(r'(?i)(?<![A-Z0-9._%+\-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![A-Z0-9._%+\-])')
URL_RE = re.compile(r'https?://[^\s<>"\']+', re.I)
CONTACT_PREFIX_RE = re.compile(r'(?i)^(?:contact\s+(?:form|link|url)|website\s+contact)\s*:\s*')
EMAIL_PREFIX_RE = re.compile(r'(?i)^(?:contact\s+)?email\s*:\s*')
GEN_NOTE_RE = re.compile(r'(?i)^discovery\s+signal\s*:\s*')
DISTINCTIVE = ('retro','legacy','niche','hard to find','hard-to-find','rare','unusual','specialist','reverse engineering','obsolete','vintage')
NON_CONTACT = ('noreply','no-reply','donotreply','do-not-reply','privacy','legal','compliance','gdpr','abuse','mailer-daemon')


def _norm_url(value):
    value=str(value or '').strip().rstrip('.,;:!?)]}')
    return value.rstrip('/').casefold()


def _usable_email(value):
    email=str(value or '').strip().lower().strip('.,;:<>[](){}')
    if not email or '@' not in email:
        return ''
    local=email.split('@',1)[0]
    if any(x.replace('-','') in local.replace('-','') for x in NON_CONTACT):
        return ''
    return email[:254]


def _clean_lead_note(note, target_url='', source_url=''):
    raw=str(note or '').strip()
    if not raw:
        return '', '', ''
    # Older generated notes often joined factual contact fields with a middle dot.
    parts=[]
    for line in raw.replace(' · ', '\n').splitlines():
        line=line.strip()
        if line:
            parts.append(line)
    keep=[]; email=''; contact_url=''
    lead_urls={_norm_url(target_url),_norm_url(source_url)}-{''}
    for part in parts:
        if re.match(r'(?i)^cloud\s+outreach\s+path\s*:',part):
            if not email:
                candidates=EMAIL_RE.findall(part)
                if candidates: email=_usable_email(candidates[0])
            if not contact_url:
                for url in URL_RE.findall(part):
                    url=url.rstrip('.,;:!?)]}')
                    if _norm_url(url) not in lead_urls:
                        contact_url=url[:1000]; break
            continue
        if EMAIL_PREFIX_RE.match(part):
            candidates=EMAIL_RE.findall(part)
            if candidates and not email:
                email=_usable_email(candidates[0])
            continue
        if EMAIL_RE.fullmatch(part.strip('.,; ')):
            if not email:
                email=_usable_email(part)
            continue
        if CONTACT_PREFIX_RE.match(part):
            urls=URL_RE.findall(part)
            for url in urls:
                url=url.rstrip('.,;:!?)]}')
                if _norm_url(url) not in lead_urls:
                    contact_url=url[:1000]
                    break
            continue
        keep.append(part)
    return '\n'.join(keep).strip(), email, contact_url


def _clean_generated_opportunity_note(note):
    raw=' '.join(str(note or '').split()).strip()
    if not raw or not GEN_NOTE_RE.match(raw):
        return note
    text=GEN_NOTE_RE.sub('',raw).strip()
    low=text.casefold()
    if not any(marker in low for marker in DISTINCTIVE):
        return ''
    if len(text)>135:
        text=text[:135].rsplit(' ',1)[0].rstrip(' ,;:-')
    return text


def backfill_v0885(apps, schema_editor):
    CompanyLead=apps.get_model('portal','CompanyLead')
    Opportunity=apps.get_model('portal','Opportunity')

    # Move contact-only generated note data into structured fields for existing leads.
    for row in CompanyLead.objects.all().iterator():
        cleaned,email,url=_clean_lead_note(row.note,row.target_url,row.source_url)
        changes={}
        if cleaned != (row.note or ''):
            changes['note']=cleaned
        if not row.contact_email and email:
            changes['contact_email']=email
        if not row.contact_url and url:
            changes['contact_url']=url
        if changes:
            CompanyLead.objects.filter(pk=row.pk).update(**changes)

    # Existing Cloud discovery notes should be as terse as newly generated ones.
    for row in Opportunity.objects.exclude(note='').only('pk','note').iterator():
        cleaned=_clean_generated_opportunity_note(row.note)
        if cleaned != row.note:
            Opportunity.objects.filter(pk=row.pk).update(note=cleaned)


class Migration(migrations.Migration):
    dependencies=[('portal','0050_v0883_company_contact_quality_backfill')]
    operations=[
        migrations.AddField(
            model_name='companylead',
            name='contact_url',
            field=models.URLField(blank=True, help_text='Direct public contact page discovered for this Hidden Lead, when different from the lead URL.', max_length=1000),
        ),
        migrations.RunPython(backfill_v0885,migrations.RunPython.noop),
    ]
