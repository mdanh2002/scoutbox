from django.db import migrations, models


def forward(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    FacebookPage=apps.get_model('portal','FacebookPage')
    UsageMetric=apps.get_model('portal','UsageMetric')
    AuditLog.objects.filter(action='scheduler_silence').delete()
    # Count a successful provider-native web-search call once when an older
    # provider response omitted its internal query list.
    UsageMetric.objects.filter(web_search_queries=0,errors=0,metadata__web_search=True).update(web_search_queries=1)
    for row in FacebookPage.objects.all().iterator():
        row.evidence_text=row.page_title or ''
        row.page_title=''
        row.is_read=True
        row.save(update_fields=['evidence_text','page_title','is_read'])
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.86').exists():
        AuditLog.objects.create(
            actor='system',action='version_upgraded',version='0.11.86',
            summary='ScoutBox upgraded to version 0.11.86.',
            metadata={'version':'0.11.86'},
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0157_v01180_multilingual_always_enabled')]
    operations=[
        migrations.AddField(model_name='auditlog',name='version',field=models.CharField(blank=True,default='',max_length=32)),
        migrations.AddField(model_name='facebookpage',name='evidence_text',field=models.TextField(blank=True,default='')),
        migrations.AddField(model_name='facebookpage',name='evidence_url',field=models.URLField(blank=True,max_length=1000)),
        migrations.AddField(model_name='facebookpage',name='is_read',field=models.BooleanField(db_index=True,default=False,help_text='Facebook Page review state. False is shown as New; True is shown as Seen.')),
        migrations.AddField(model_name='facebookpage',name='deleted_at',field=models.DateTimeField(blank=True,db_index=True,help_text='When this Facebook Page was moved to the Recycle Bin.',null=True)),
        migrations.AddField(model_name='trackinglink',name='deleted_at',field=models.DateTimeField(blank=True,db_index=True,help_text='When this tracking link was moved to the Recycle Bin.',null=True)),
        migrations.RunPython(forward,migrations.RunPython.noop),
    ]
