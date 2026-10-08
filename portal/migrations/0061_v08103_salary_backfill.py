from django.db import migrations, models
from django.utils import timezone


def retained_salary_backfill(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    # Import the runtime helper so upgrades immediately recover compensation already
    # retained in Cloud discovery/JD evidence. This helper is deterministic and performs
    # no network or AI calls, so migrations remain safe while workers are running.
    try:
        from portal.services.salary import salary_from_retained_opportunity
    except Exception:
        return
    batch=[]
    for row in Opportunity.objects.all().iterator(chunk_size=250):
        try:
            info=salary_from_retained_opportunity(row)
        except Exception:
            info={}
        if not info:
            # Every legacy Opportunity is examined during the upgrade. Missing pay data is
            # a valid result, not a migration failure. Mark the retained-evidence check so
            # the list can say "Salary not found" rather than looking unprocessed.
            if not row.salary_checked_at:
                row.salary_checked_at=timezone.now(); row.salary_source_type=row.salary_source_type or 'unknown'
                batch.append(row)
                if len(batch)>=250:
                    Opportunity.objects.bulk_update(batch,['salary_text','salary_currency','salary_min','salary_max','salary_period','salary_source_type','salary_source_url','salary_confidence','salary_checked_at'],batch_size=250)
                    batch=[]
            continue
        changed=False
        for field in ('salary_text','salary_currency','salary_min','salary_max','salary_period','salary_source_type','salary_source_url','salary_confidence','salary_checked_at'):
            value=info.get(field)
            if value not in (None,'') and getattr(row,field,None) in (None,'',0):
                setattr(row,field,value); changed=True
        if changed:
            batch.append(row)
            if len(batch)>=250:
                Opportunity.objects.bulk_update(batch,['salary_text','salary_currency','salary_min','salary_max','salary_period','salary_source_type','salary_source_url','salary_confidence','salary_checked_at'],batch_size=250)
                batch=[]
    if batch:
        Opportunity.objects.bulk_update(batch,['salary_text','salary_currency','salary_min','salary_max','salary_period','salary_source_type','salary_source_url','salary_confidence','salary_checked_at'],batch_size=250)


class Migration(migrations.Migration):
    dependencies=[('portal','0060_v08102_digest_recipient')]
    operations=[
        migrations.AddField(model_name='portalsettings',name='release_backfill_version',field=models.CharField(blank=True,default='',help_text='Last release-level enrichment backfill queued for this installation.',max_length=32)),
        migrations.AddField(model_name='opportunity',name='salary_text',field=models.CharField(blank=True,default='',help_text='Compact advertised or researched compensation text for list display.',max_length=300)),
        migrations.AddField(model_name='opportunity',name='salary_currency',field=models.CharField(blank=True,default='',max_length=12)),
        migrations.AddField(model_name='opportunity',name='salary_min',field=models.DecimalField(blank=True,decimal_places=2,max_digits=14,null=True)),
        migrations.AddField(model_name='opportunity',name='salary_max',field=models.DecimalField(blank=True,decimal_places=2,max_digits=14,null=True)),
        migrations.AddField(model_name='opportunity',name='salary_period',field=models.CharField(blank=True,default='',max_length=24)),
        migrations.AddField(model_name='opportunity',name='salary_source_type',field=models.CharField(blank=True,default='',help_text='post, external, market, or unknown.',max_length=24)),
        migrations.AddField(model_name='opportunity',name='salary_source_url',field=models.URLField(blank=True,default='',max_length=1000)),
        migrations.AddField(model_name='opportunity',name='salary_confidence',field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name='opportunity',name='salary_checked_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.RunPython(retained_salary_backfill,migrations.RunPython.noop),
    ]
