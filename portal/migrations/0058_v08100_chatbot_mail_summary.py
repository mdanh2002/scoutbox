from django.db import migrations, models


def _mail_server_for_event(event, profiles):
    meta=event.metadata if isinstance(event.metadata,dict) else {}
    template=str(meta.get('template') or meta.get('mailbox_template') or '').strip()
    profile=next((p for p in profiles if str(p.template)==template),None)
    if profile is None:
        # Older rows did not persist the profile key. Prefer a profile whose mailbox
        # identity occurs in the sender/recipient fields, otherwise use the active one.
        hay=(' '+str(event.sender or '')+' '+str(event.recipients or '')+' ').casefold()
        profile=next((p for p in profiles if p.imap_email and str(p.imap_email).casefold() in hay),None)
    if profile is None:
        profile=next((p for p in profiles if p.active),None) or (profiles[0] if profiles else None)
    if event.kind=='notification':
        host=str(meta.get('smtp_host') or (profile.smtp_host if profile else '') or '').strip()
        port=meta.get('smtp_port') or (profile.smtp_port if profile else None)
        return (f'SMTP {host}:{port}' if host and port else (f'SMTP {host}' if host else ''))[:300]
    host=str(profile.imap_host if profile else '').strip()
    port=profile.imap_port if profile else None
    return (f'IMAP {host}:{port}' if host and port else (f'IMAP {host}' if host else ''))[:300]


def backfill(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    MailEvent=apps.get_model('portal','MailEvent')
    EmailProfile=apps.get_model('portal','EmailProfile')

    # Backfill only empty list summaries. Cloud rows prefer wording already produced by
    # Cloud AI; Local rows use the same source-grounded deterministic fallback as the
    # live Local AI pipeline. No existing non-empty summary is overwritten.
    from portal.services.highlights import derive_opportunity_highlight, normalize_ai_fit_summary
    batch=[]
    for row in Opportunity.objects.filter(list_highlight='').iterator(chunk_size=250):
        facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
        value=''
        if bool(facts.get('cloud_discovery')):
            cloud=facts.get('cloud_research') if isinstance(facts.get('cloud_research'),dict) else {}
            fit=facts.get('fit_classification') if isinstance(facts.get('fit_classification'),dict) else {}
            ai=facts.get('ai_job_summary') if isinstance(facts.get('ai_job_summary'),dict) else {}
            for candidate in (
                cloud.get('summary'), fit.get('reason'), row.recommendation_reason,
                ai.get('text'), row.note,
            ):
                value=normalize_ai_fit_summary(candidate,max_words=50)
                if value:
                    break
        if not value:
            value=derive_opportunity_highlight(opportunity=row)[:300]
        if value:
            row.list_highlight=value[:300]
            batch.append(row)
            if len(batch)>=250:
                Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=250)
                batch=[]
    if batch:
        Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=250)

    profiles=list(EmailProfile.objects.all())
    mail_batch=[]
    for event in MailEvent.objects.filter(server='').iterator(chunk_size=300):
        event.server=_mail_server_for_event(event,profiles)
        if event.server:
            mail_batch.append(event)
            if len(mail_batch)>=300:
                MailEvent.objects.bulk_update(mail_batch,['server'],batch_size=300)
                mail_batch=[]
    if mail_batch:
        MailEvent.objects.bulk_update(mail_batch,['server'],batch_size=300)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0057_v0899_rebuild_relevance_health')]
    operations=[
        migrations.AddField(
            model_name='mailevent',
            name='server',
            field=models.CharField(blank=True,default='',help_text='Mail server/protocol used for this event, such as IMAP host:port or SMTP host:port.',max_length=300),
        ),
        migrations.RunPython(backfill,noop),
    ]
