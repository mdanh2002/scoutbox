from django.db import migrations, models
from django.utils import timezone
import re


def migrate_addressbook_provenance(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    Contact=apps.get_model('portal','Contact')
    for row in AuditLog.objects.filter(action='addressbook_promotion').order_by('at').iterator():
        meta=row.metadata if isinstance(row.metadata,dict) else {}
        email=str(meta.get('email') or '').strip()
        if not email:
            continue
        contact=Contact.objects.filter(email__iexact=email).first()
        if not contact:
            continue
        provenance=contact.origin_provenance if isinstance(contact.origin_provenance,dict) else {}
        provenance=dict(provenance)
        provenance.update({
            'campaign_id':meta.get('campaign_id') or provenance.get('campaign_id'),
            'campaign_run_id':meta.get('campaign_run_id') or provenance.get('campaign_run_id'),
            'source':meta.get('source') or provenance.get('source') or '',
            'source_url':meta.get('source_url') or provenance.get('source_url') or '',
            'promoted_at':row.at.isoformat() if row.at else provenance.get('promoted_at'),
        })
        contact.origin_provenance=provenance
        contact.save(update_fields=['origin_provenance'])
    AuditLog.objects.filter(action='addressbook_promotion').delete()


def _plausible_company(value):
    text=' '.join(str(value or '').split()).strip(' -–—|:;,')[:220]
    if len(text)<2 or len(text)>120:
        return ''
    low=text.casefold()
    bad=('about the role','responsibilities','requirements','experience with','we are hiring','we are seeking',
         'job description','software engineer will','the role','apply now','salary','benefits','http://','https://',
         ':title',':description','{crawled','json','github gist')
    if any(x in low for x in bad):
        return ''
    if len(text.split())>10 or text.count('.')>1 or text.count('{') or text.count('}'):
        return ''
    if not any(ch.isalpha() for ch in text):
        return ''
    return text


def _recover_company(blob):
    text=' '.join(str(blob or '').split())
    patterns=(
        r'\bAbout the Role\s+([A-Z][A-Za-z0-9&.+\'’\- ]{1,70}?)(?=\s+(?:is|seeks|builds|provides|develops|offers|\||[-–—])|[.,;:]|$)',
        r'\b([A-Z][A-Za-z0-9&.+\'’\- ]{1,70}?)\s+(?:is|are)\s+(?:hiring|seeking|looking for|recruiting)\b',
    )
    for pattern in patterns:
        match=re.search(pattern,text)
        if match:
            candidate=_plausible_company(match.group(1))
            if candidate:
                return candidate
    return ''


def repair_recent_opportunity_identity(apps, schema_editor):
    """Repair only deterministic 0.10.93 identity failures; never invoke AI/network."""
    Opportunity=apps.get_model('portal','Opportunity')
    now=timezone.now()
    serialized_markers=(':title',':description','{:crawled','"title"','"description"','crawled true','crawled:true')
    for row in Opportunity.objects.filter(user_deleted=False).iterator():
        title=str(row.title or '')
        urls=' '.join(str(x or '') for x in (row.url,row.target_url,row.search_url,row.canonical_url)).casefold()
        title_low=title.casefold()
        gist_dataset=('gist.github.com' in urls and (any(m in title_low for m in serialized_markers) or len(title)>220))
        serialized_title=(any(m in title_low for m in serialized_markers) and len(title)>120)
        if gist_dataset or serialized_title:
            row.suppressed=True
            row.status='rejected'
            row.rejection_reason='invalid_opportunity_source: serialized/job-dataset page'
            row.user_deleted=True
            row.deleted_at=now
            row.save(update_fields=['suppressed','status','rejection_reason','user_deleted','deleted_at','updated_at'])
            continue
        company=_plausible_company(row.company)
        if not company:
            evidence=' '.join(str(x or '') for x in (row.company,row.raw_search_snippet,row.list_highlight,row.description,title))
            recovered=_recover_company(evidence)
            if recovered and recovered != row.company:
                row.company=recovered
                row.save(update_fields=['company','updated_at'])


def mark_domain_age_refresh(apps, schema_editor):
    """Make legacy company cards eligible to collect domain-age tooltip evidence later."""
    for model_name in ('Opportunity','CompanyLead','Contact'):
        Model=apps.get_model('portal',model_name)
        for row in Model.objects.exclude(company_intel={}).iterator():
            intel=row.company_intel if isinstance(row.company_intel,dict) else {}
            structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
            if structured.get('domain_age_years') not in (None,'') or structured.get('domain_registered_at'):
                continue
            # Only mark rows that already have a company/domain hint; this is a refresh hint,
            # not permission to infer a domain from an arbitrary job board URL.
            sources=intel.get('sources') if isinstance(intel.get('sources'),list) else []
            has_domain=bool(structured.get('domain_age_domain') or structured.get('website') or intel.get('website'))
            if not has_domain:
                has_domain=any(isinstance(x,dict) and str(x.get('url') or '').startswith(('http://','https://')) for x in sources)
            if not has_domain:
                continue
            updated=dict(intel); st=dict(structured); st['domain_age_refresh_needed']=True; updated['structured']=st
            row.company_intel=updated
            row.save(update_fields=['company_intel'])


class Migration(migrations.Migration):
    dependencies=[('portal','0116_v01093_addressbook_summary_backfill')]
    operations=[
        migrations.AddField(model_name='portalsettings',name='detailed_log_retention_days',field=models.PositiveSmallIntegerField(default=90,help_text='Retention for detailed operational logs and resource telemetry. UI clamp: 14-180 days.')),
        migrations.AddField(model_name='portalsettings',name='scheduler_health',field=models.JSONField(blank=True,default=dict,help_text='Recent scheduler/worker health summary used by diagnostics.')),
        migrations.AddField(model_name='contact',name='origin_provenance',field=models.JSONField(blank=True,default=dict,help_text='Lightweight campaign/run/source provenance for automatic Address Book promotion.')),
        migrations.RunPython(migrate_addressbook_provenance,migrations.RunPython.noop),
        migrations.RunPython(repair_recent_opportunity_identity,migrations.RunPython.noop),
        migrations.RunPython(mark_domain_age_refresh,migrations.RunPython.noop),
    ]
