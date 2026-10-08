from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def seed_v080(apps, schema_editor):
    Profile=apps.get_model('portal','Profile')
    Campaign=apps.get_model('portal','Campaign')
    CampaignTemplate=apps.get_model('portal','CampaignTemplate')
    SearchSource=apps.get_model('portal','SearchSource')
    FacebookConfig=apps.get_model('portal','FacebookConfig')
    FacebookPage=apps.get_model('portal','FacebookPage')
    TrackingLinkRule=apps.get_model('portal','TrackingLinkRule')

    p=Profile.objects.filter(pk=1).first()
    if p and not p.operating_locations:
        p.operating_locations=[p.operating_location] if p.operating_location else ['Singapore']
        p.save(update_fields=['operating_locations'])

    for c in Campaign.objects.all():
        changed=[]
        if not c.locations:
            c.locations=[c.location] if c.location else []
            changed.append('locations')
        if changed:
            c.save(update_fields=changed)

    if SearchSource.objects.exists() and not SearchSource.objects.filter(enabled=True).exists():
        SearchSource.objects.filter(low_value_marketplace=False).update(enabled=True)
        SearchSource.objects.filter(low_value_marketplace=True).update(enabled=False)

    builtins={
        'Embedded Remote by Region': ('Embedded and firmware roles with low-level systems emphasis', ['embedded systems','firmware / hardware'], ['PIC','STM32','ESP32','RTOS','Embedded Linux']),
        'Reverse Engineering': ('Reverse engineering, binary and firmware analysis', ['reverse engineering','systems software'], ['Binary analysis','Firmware analysis','Legacy protocols','x86']),
        'Retro / Legacy Systems': ('Retro computing, emulation and legacy systems', ['retro / legacy systems','systems software'], ['DOS','BIOS','QEMU','MAME','x86']),
        'Technical Writing': ('Technical writing and developer education', ['technical writing'], ['Embedded Linux','Reverse engineering']),
        'Remote Teaching / Training': ('Remote technical teaching and training', ['teaching / training'], ['Embedded Linux','Systems software']),
    }
    for name,(desc,roles,tech) in builtins.items():
        old=Campaign.objects.filter(name=name).first()
        defaults={
            'description':desc,'built_in':True,'locations':old.locations if old else [],
            'role_families':roles,'technologies':tech,
            'engagement_types':['Full-time','Part-time','Contract','Collaboration'],
            'company_sizes':['Small','Startup','Medium','Unknown'],
            'languages':[], 'negative_constraints':old.negative_constraints if old else '',
            'extra_text':old.extra_text if old else '', 'recency_days':old.recency_days if old else 30,
            'source_names':old.source_names if old else [],
        }
        CampaignTemplate.objects.get_or_create(name=name, defaults=defaults)

    fb=FacebookConfig.objects.filter(pk=1).first()
    if fb and fb.graph_page_ids:
        import re
        for page_id in [x.strip() for x in re.split(r'[,;\n]+',fb.graph_page_ids) if x.strip()]:
            FacebookPage.objects.get_or_create(page_id=page_id)

    TrackingLinkRule.objects.get_or_create(
        name='Automatic ToughDev blog tracking',
        defaults={'base_path':'/blog','destination_url':'https://toughdev.com/blog','article_title':'','article_keywords':'','enabled':True},
    )


class Migration(migrations.Migration):
    dependencies=[('portal','0001_initial')]
    operations=[
        migrations.AddField(model_name='portalsettings',name='tracking_blog_base_url',field=models.URLField(blank=True,default='https://toughdev.com/blog',max_length=1000)),
        migrations.AddField(model_name='profile',name='operating_locations',field=models.JSONField(blank=True,default=list,help_text='Searchable list of countries/regions where the candidate can operate.')),
        migrations.AddField(model_name='searchsource',name='api_key_enc',field=models.TextField(blank=True,help_text='Legacy reserved field; v0.8.1 search-provider credentials are read from .env.')),
        migrations.AddField(model_name='searchsource',name='public_fallback',field=models.BooleanField(default=True,help_text='Allow limited public HTML search when no API key is configured and the provider supports it.')),
        migrations.AddField(model_name='campaign',name='locations',field=models.JSONField(blank=True,default=list)),
        migrations.AddField(model_name='campaign',name='queries_per_rotation',field=models.PositiveIntegerField(blank=True,help_text='Optional campaign-specific query bundle size; blank inherits the portal default.',null=True)),
        migrations.AddField(model_name='contact',name='phone',field=models.CharField(blank=True,max_length=80)),
        migrations.CreateModel(
            name='BackgroundJob',
            fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('kind',models.CharField(choices=[('campaign','Campaign discovery'),('import_text','Application import'),('import_document','Document import'),('mail_scan','Mailbox scan'),('diagnostic','Test discovery'),('other','Automatic task')],default='other',max_length=30)),('label',models.CharField(max_length=300)),('status',models.CharField(choices=[('queued','Queued'),('running','Running'),('completed','Completed'),('failed','Failed'),('stopped','Stopped')],default='queued',max_length=20)),('celery_task_id',models.CharField(blank=True,max_length=120)),('progress',models.PositiveSmallIntegerField(default=0)),('message',models.CharField(blank=True,max_length=500)),('result',models.JSONField(blank=True,default=dict)),('error',models.TextField(blank=True)),('created_at',models.DateTimeField(auto_now_add=True)),('started_at',models.DateTimeField(blank=True,null=True)),('finished_at',models.DateTimeField(blank=True,null=True))],
            options={'ordering':['-created_at']},
        ),
        migrations.CreateModel(
            name='CampaignTemplate',
            fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('name',models.CharField(max_length=200,unique=True)),('description',models.CharField(blank=True,max_length=500)),('built_in',models.BooleanField(default=False)),('locations',models.JSONField(blank=True,default=list)),('role_families',models.JSONField(blank=True,default=list)),('technologies',models.JSONField(blank=True,default=list)),('engagement_types',models.JSONField(blank=True,default=list)),('company_sizes',models.JSONField(blank=True,default=list)),('languages',models.JSONField(blank=True,default=list)),('negative_constraints',models.TextField(blank=True)),('extra_text',models.TextField(blank=True)),('recency_days',models.PositiveIntegerField(default=30)),('source_names',models.JSONField(blank=True,default=list)),('queries_per_rotation',models.PositiveIntegerField(blank=True,null=True)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True))],
            options={'ordering':['name']},
        ),
        migrations.CreateModel(
            name='FacebookPage',
            fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('page_id',models.CharField(max_length=120,unique=True)),('page_url',models.URLField(blank=True,max_length=1000)),('page_title',models.CharField(blank=True,max_length=300)),('enabled',models.BooleanField(default=True)),('discovered_at',models.DateTimeField(default=django.utils.timezone.now)),('updated_at',models.DateTimeField(auto_now=True))],
            options={'ordering':['page_title','page_id']},
        ),
        migrations.CreateModel(
            name='CampaignRun',
            fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('status',models.CharField(choices=[('queued','Queued'),('running','Running'),('stopping','Stopping'),('completed','Completed'),('failed','Failed'),('stopped','Stopped')],default='queued',max_length=20)),('celery_task_id',models.CharField(blank=True,max_length=120)),('progress',models.PositiveSmallIntegerField(default=0)),('message',models.CharField(blank=True,max_length=500)),('criteria',models.JSONField(blank=True,default=dict)),('query_plan',models.JSONField(blank=True,default=dict)),('result',models.JSONField(blank=True,default=dict)),('error',models.TextField(blank=True)),('started_at',models.DateTimeField(blank=True,null=True)),('finished_at',models.DateTimeField(blank=True,null=True)),('created_at',models.DateTimeField(auto_now_add=True)),('campaign',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='runs',to='portal.campaign'))],
            options={'ordering':['-created_at']},
        ),
        migrations.RunPython(seed_v080,migrations.RunPython.noop),
    ]
