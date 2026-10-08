from django.db import migrations, models


def repair_retained_salary(apps, schema_editor):
    """Prefer retained JD/source compensation over earlier external estimates.

    This migration is intentionally network/AI-free so it is safe while Local Discovery
    is configured or running. It only reparses evidence already stored in ScoutBox.
    """
    Opportunity=apps.get_model('portal','Opportunity')
    try:
        from portal.services.salary import salary_from_retained_opportunity
    except Exception:
        return
    fields=['salary_text','salary_currency','salary_min','salary_max','salary_period','salary_source_type','salary_source_url','salary_confidence','salary_checked_at']
    batch=[]
    for row in Opportunity.objects.filter(user_deleted=False).iterator(chunk_size=250):
        try:
            info=salary_from_retained_opportunity(row)
        except Exception:
            info={}
        if not info:
            continue
        for field in fields:
            if field in info:
                setattr(row,field,info.get(field))
        batch.append(row)
        if len(batch)>=250:
            Opportunity.objects.bulk_update(batch,fields,batch_size=250)
            batch=[]
    if batch:
        Opportunity.objects.bulk_update(batch,fields,batch_size=250)


class Migration(migrations.Migration):
    dependencies=[('portal','0063_v08103_summary_punctuation_backfill')]
    operations=[
        migrations.AddField(
            model_name='portalsettings',
            name='portal_root_url',
            field=models.URLField(blank=True,default='http://localhost:8989',help_text='Absolute ScoutBox root used in email and notification links.',max_length=1000),
        ),
        migrations.AlterField(
            model_name='opportunity',
            name='salary_source_type',
            field=models.CharField(blank=True,default='',help_text='post, job_estimate, external, market, or unknown.',max_length=24),
        ),
        migrations.AlterField(
            model_name='backgroundjob',
            name='kind',
            field=models.CharField(choices=[('campaign','Campaign discovery'),('import_text','Application import'),('import_document','Document import'),('mail_scan','Mailbox scan'),('diagnostic','Test discovery'),('hidden_scan','Hidden Leads scan'),('cold_draft','Cold outreach draft'),('enrich','Opportunity enrichment'),('prepare','Application preparation'),('translate','Translation'),('company_research','Company research'),('summarize','AI text summary'),('performance','Performance test'),('chatbot','Chatbot request'),('other','Automatic task')],default='other',max_length=30),
        ),
        migrations.RunPython(repair_retained_salary,migrations.RunPython.noop),
    ]
