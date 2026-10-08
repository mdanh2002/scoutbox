from django.db import migrations, models
from django.utils import timezone
import re


def suppress_obvious_job_collections(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    pattern=re.compile(r'^\s*(?:\d{1,3}(?:[,.]\d{3})+|\d+)\+?\s+.+?\bjobs?\b',re.I)
    ids=[]
    for row in Opportunity.objects.filter(suppressed=False).only('id','title'):
        if pattern.search(row.title or ''):
            ids.append(row.id)
    if ids:
        Opportunity.objects.filter(id__in=ids).update(suppressed=True,rejection_reason='Multi-job listing/aggregator page; individual roles must be expanded before persistence.')


class Migration(migrations.Migration):
    dependencies=[('portal','0026_v0829_campaign_leads_phone_cleanup')]
    operations=[
        migrations.AddField(model_name='opportunity',name='user_deleted',field=models.BooleanField(db_index=True,default=False,help_text='Soft-delete tombstone set when a user removes this opportunity from ScoutBox.')),
        migrations.AddField(model_name='opportunity',name='deleted_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='companylead',name='user_deleted',field=models.BooleanField(db_index=True,default=False,help_text='Soft-delete tombstone set when a user removes this Hidden Lead from ScoutBox.')),
        migrations.AddField(model_name='companylead',name='deleted_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.RunPython(suppress_obvious_job_collections,migrations.RunPython.noop),
    ]
