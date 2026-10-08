from django.db import migrations
from django.utils import timezone


MULTI_ACCESS = {
    'Yandex': {'public','yandex_api_key','yandex_iam'},
    'Baidu': {'public','baidu_qianfan'},
    'Naver': {'public','naver_legacy','naver_hub'},
}


HISTORY_STATUSES={'applied','reply','interview','rejected','accepted','closed'}


def forwards(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Opportunity=apps.get_model('portal','Opportunity')
    Application=apps.get_model('portal','Application')

    # Multi-access search engines must never render with a blank access selection.
    for source in SearchSource.objects.filter(name__in=MULTI_ACCESS):
        cfg=dict(source.config_json or {})
        selected=str(cfg.get('access_type') or '').strip()
        if selected not in MULTI_ACCESS[source.name]:
            cfg['access_type']='public'
            source.config_json=cfg
            source.save(update_fields=['config_json'])

    # Rebuild automated Market Studies prose under the v0.8.23 natural-summary rules.
    # Manual leads (no search provenance) keep the user's text.
    CompanyLead.objects.exclude(search_url='').update(summary='')

    # Earlier releases stored Prepare Outreach output only on CompanyLead. Backfill those
    # drafts into the unified Applications & Outreach tracker so no generated communication
    # remains stranded on the Market Studies record after upgrade.
    outreach_opps={}
    for opp in Opportunity.objects.all().only('pk','extracted_facts'):
        facts=opp.extracted_facts or {}
        lead_id=facts.get('market_study_lead_id')
        if facts.get('outreach') is True and str(lead_id).isdigit():
            outreach_opps[int(lead_id)]=opp

    for lead in CompanyLead.objects.all():
        if not (str(lead.draft_subject or '').strip() or str(lead.draft_body or '').strip()):
            continue
        opp=outreach_opps.get(lead.pk)
        target=(lead.target_url or lead.source_url or f'https://manual.invalid/market-outreach-{lead.pk}').strip()
        if not opp:
            opp=Opportunity.objects.create(
                title='Direct outreach', company=lead.company, country=lead.country, url=target,
                canonical_url=target if target.startswith(('http://','https://')) and 'manual.invalid' not in target else '',
                target_url=target if target.startswith(('http://','https://')) and 'manual.invalid' not in target else '',
                search_url=lead.search_url, channel='email', contact_email=lead.contact_email, contact_name=lead.contact_name,
                description='\n\n'.join(x for x in [lead.summary,lead.match_summary,lead.evidence] if str(x or '').strip())[:30000],
                status='draft', fit_score=lead.score, is_read=True, application_draft_requested_at=timezone.now(),
                extracted_facts={'market_study_lead_id':lead.pk,'outreach':True},
            )
            outreach_opps[lead.pk]=opp
        app=Application.objects.filter(opportunity_id=opp.pk).first()
        if not app:
            app=Application.objects.create(opportunity_id=opp.pk,status='prepared',is_read=False)
        updates={
            'email_subject':lead.draft_subject or app.email_subject,
            'email_body':lead.draft_body or app.email_body,
            'email_mode':'plain',
            'is_read':False,
        }
        if app.status not in HISTORY_STATUSES:
            updates['status']='prepared'
        Application.objects.filter(pk=app.pk).update(**updates)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0019_v0822_provider_public_default')]
    operations=[migrations.RunPython(forwards,backwards)]
