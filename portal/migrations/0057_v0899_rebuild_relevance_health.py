import re
from urllib.parse import urlsplit
from django.db import migrations

_JOB_BOARD_BRANDS={
    'indeed','glassdoor','linkedin','ziprecruiter','simplyhired','talent','jooble',
    'jobrapido','careerjet','monster','jobs2careers','adzuna','jobisjob','jobted','bebee',
}
_TECHNICAL_TITLE_RE=re.compile(
    r'(?i)\b(?:engineer|engineering|developer|programmer|architect|researcher|security|firmware|embedded|kernel|'
    r'systems?|software|technical\s+(?:writer|author|trainer|instructor)|documentation\s+engineer|developer\s+documentation|devrel|'
    r'reverse\s+engineer|virtuali[sz]ation)\b'
)


def _job_board(url):
    try:
        host=(urlsplit(str(url or '')).netloc or '').lower().removeprefix('www.')
    except Exception:
        return False
    labels={x for x in host.split('.') if x}
    return bool(labels.intersection(_JOB_BOARD_BRANDS))


def rebuild(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    Application=apps.get_model('portal','Application')
    CompanyLead=apps.get_model('portal','CompanyLead')
    from portal.services.highlights import derive_opportunity_highlight

    application_opportunity_ids=set(Application.objects.values_list('opportunity_id',flat=True))
    batch=[]
    for row in Opportunity.objects.all().iterator(chunk_size=250):
        facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
        # Some historical rows retained fetched JD text only inside the AI evidence payload.
        # Restore that source-backed text when the visible description field is empty.
        if not str(row.description or '').strip():
            ai=facts.get('ai_job_summary') if isinstance(facts.get('ai_job_summary'),dict) else {}
            source_text=str(ai.get('source_text') or '').strip()
            if source_text:
                row.description=source_text[:45000]

        row.list_highlight=derive_opportunity_highlight(opportunity=row)[:300]

        # Clean obvious Local AI false positives from multi-employer boards. Do not touch
        # Cloud discoveries, manual/imported rows, or anything already linked to an application.
        provenance=bool(facts.get('discovery_query') or facts.get('discovery_provenance'))
        cloud=bool(facts.get('cloud_discovery'))
        candidate_url=row.target_url or row.url or row.search_url or ''
        if (not row.user_deleted and not row.suppressed and provenance and not cloud
                and row.pk not in application_opportunity_ids and _job_board(candidate_url)
                and not _TECHNICAL_TITLE_RE.search(str(row.title or ''))):
            row.suppressed=True
            row.status='rejected'
            row.rejection_reason=(
                'Filtered by ScoutBox 0.8.99 relevance cleanup: a general job-board role had '
                'no grounded candidate-profile evidence in its title or stored job description.'
            )[:2000]
        batch.append(row)
        if len(batch)>=250:
            Opportunity.objects.bulk_update(
                batch,['description','list_highlight','suppressed','status','rejection_reason'],batch_size=250
            )
            batch=[]
    if batch:
        Opportunity.objects.bulk_update(
            batch,['description','list_highlight','suppressed','status','rejection_reason'],batch_size=250
        )

    # Make legacy leads with a real URL immediately eligible for a fresh background health
    # check. This is especially useful for rows created before discovery persisted the HTTP
    # result it had already fetched.
    lead_batch=[]
    for lead in CompanyLead.objects.all().iterator(chunk_size=300):
        changed=False
        if not str(lead.target_url or '').strip() and str(lead.source_url or '').strip():
            lead.target_url=lead.source_url
            changed=True
        if lead.target_http_status is None and not str(lead.target_check_error or '').strip():
            if lead.target_checked_at is not None:
                lead.target_checked_at=None
                changed=True
        if changed:
            lead_batch.append(lead)
            if len(lead_batch)>=300:
                CompanyLead.objects.bulk_update(lead_batch,['target_url','target_checked_at'],batch_size=300)
                lead_batch=[]
    if lead_batch:
        CompanyLead.objects.bulk_update(lead_batch,['target_url','target_checked_at'],batch_size=300)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0056_v0898_digest_highlight_cleanup')]
    operations=[migrations.RunPython(rebuild,noop)]
