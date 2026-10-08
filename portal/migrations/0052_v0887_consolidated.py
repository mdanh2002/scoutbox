from django.db import migrations, models
import django.db.models.deletion


def migrate_defaults(apps, schema_editor):
    S=apps.get_model('portal','PortalSettings')
    row=S.objects.filter(pk=1).first()
    if not row: return
    mapping={
        'cloud_deep_research_candidates_per_run':(250,100),
        'cloud_page_recovery_per_day':(500,250),
        'cloud_auto_runs_per_campaign_day':(16,5),
        'cloud_min_interval_minutes':(60,240),
        'cloud_daily_requests':(2000,1000),
        'cloud_daily_input_tokens':(5000000,3000000),
        'cloud_daily_output_tokens':(2000000,1000000),
    }
    changed=[]
    for field,(old,new) in mapping.items():
        if getattr(row,field,None)==old:
            setattr(row,field,new); changed.append(field)
    if changed: row.save(update_fields=changed+['updated_at'])



def link_legacy_resume_templates(apps, schema_editor):
    import re
    DocumentAsset=apps.get_model('portal','DocumentAsset')
    CampaignTemplate=apps.get_model('portal','CampaignTemplate')
    for asset in DocumentAsset.objects.filter(kind='cv'):
        marker=f'[Generated from Resume #{asset.pk}]'
        row=CampaignTemplate.objects.filter(description__startswith=marker).order_by('-updated_at','-pk').first()
        if row:
            row.source_resume_id=asset.pk
            row.save(update_fields=['source_resume'])
            asset.campaign_template_generated_at=row.updated_at or row.created_at
            asset.save(update_fields=['campaign_template_generated_at'])

class Migration(migrations.Migration):
    dependencies=[('portal','0051_v0885_contact_note_cleanup')]
    operations=[
        migrations.AlterField(model_name='portalsettings',name='cloud_deep_research_candidates_per_run',field=models.PositiveIntegerField(default=100)),
        migrations.AlterField(model_name='portalsettings',name='cloud_page_recovery_per_day',field=models.PositiveIntegerField(default=250)),
        migrations.AlterField(model_name='portalsettings',name='cloud_auto_runs_per_campaign_day',field=models.PositiveIntegerField(default=5)),
        migrations.AlterField(model_name='portalsettings',name='cloud_min_interval_minutes',field=models.PositiveIntegerField(default=240)),
        migrations.AlterField(model_name='portalsettings',name='cloud_daily_requests',field=models.PositiveIntegerField(default=1000)),
        migrations.AlterField(model_name='portalsettings',name='cloud_daily_input_tokens',field=models.PositiveIntegerField(default=3000000)),
        migrations.AlterField(model_name='portalsettings',name='cloud_daily_output_tokens',field=models.PositiveIntegerField(default=1000000)),
        migrations.AddField(model_name='documentasset',name='campaign_template_generated_at',field=models.DateTimeField(blank=True,null=True,help_text='Most recent successful Campaign Template generation from this Resume.')),
        migrations.AddField(model_name='campaigntemplate',name='source_resume',field=models.ForeignKey(blank=True,help_text='Resume that generated this template. Cleared if the Resume is deleted; template remains independent.',null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='generated_campaign_templates',to='portal.documentasset')),
        migrations.AddField(model_name='contact',name='domain_http_status',field=models.PositiveSmallIntegerField(blank=True,help_text='Most recent HTTP status observed for the email domain.',null=True)),
        migrations.AddField(model_name='contact',name='domain_checked_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='contact',name='domain_check_error',field=models.CharField(blank=True,default='',max_length=500)),
        migrations.CreateModel(name='ChatbotMessage',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('session_key',models.CharField(blank=True,db_index=True,max_length=120)),('role',models.CharField(choices=[('user','User'),('assistant','Assistant')],max_length=20)),('text',models.TextField()),('links',models.JSONField(blank=True,default=list)),('at',models.DateTimeField(db_index=True,auto_now_add=True))],options={'ordering':['at','id']}),
        migrations.CreateModel(name='ApplicationStatusEvent',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('old_status',models.CharField(blank=True,max_length=30)),('new_status',models.CharField(max_length=30)),('at',models.DateTimeField(db_index=True,auto_now_add=True)),('source',models.CharField(blank=True,default='application',max_length=80)),('application',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='status_events',to='portal.application'))],options={'ordering':['-at']}),
        migrations.CreateModel(name='UsageThresholdNotification',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('period_key',models.CharField(db_index=True,max_length=80)),('metric_key',models.CharField(db_index=True,max_length=120)),('metric_label',models.CharField(blank=True,max_length=200)),('threshold',models.PositiveSmallIntegerField()),('used',models.PositiveBigIntegerField(default=0)),('limit',models.PositiveBigIntegerField(default=0)),('campaign_name',models.CharField(blank=True,max_length=200)),('sent_at',models.DateTimeField(auto_now_add=True))],options={'ordering':['-sent_at'],'unique_together':{('period_key','metric_key','threshold')}}),
        migrations.RunPython(migrate_defaults,migrations.RunPython.noop),
        migrations.RunPython(link_legacy_resume_templates,migrations.RunPython.noop),
    ]
