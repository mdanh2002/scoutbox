from django.db import migrations, models

DEFAULT_BLACKLIST = [
    ('wikipedia.org', 'Wikipedia', 'Reference/encyclopedia content; not an opportunity source.'),
    ('en.wikipedia.org', 'Wikipedia', 'Reference/encyclopedia content; not an opportunity source.'),
    ('learn.microsoft.com', 'Microsoft Learn', 'Technical documentation.'),
    ('msdn.microsoft.com', 'MSDN', 'Technical documentation/archive.'),
    ('docs.microsoft.com', 'Microsoft Docs', 'Technical documentation.'),
    ('developer.mozilla.org', 'MDN', 'Technical documentation.'),
    ('docs.python.org', 'Python Docs', 'Technical documentation.'),
    ('docs.oracle.com', 'Oracle Docs', 'Technical documentation.'),
    ('docs.github.com', 'GitHub Docs', 'Technical documentation.'),
    ('support.google.com', 'Google Help', 'Support/documentation content.'),
    ('cloud.google.com/docs', 'Google Cloud Docs', 'Technical documentation.'),
    ('docs.aws.amazon.com', 'AWS Docs', 'Technical documentation.'),
    ('developer.apple.com/documentation', 'Apple Developer Docs', 'Technical documentation.'),
    ('man7.org', 'Linux man-pages', 'Technical manual content.'),
    ('r-project.org', 'R Project manuals', 'Technical/manual content, not job listings.'),
    ('cran.r-project.org', 'CRAN', 'Package/manual content, not job listings.'),
    ('youtube.com', 'YouTube', 'Video/media pages are too noisy for opportunity discovery.'),
    ('music.youtube.com', 'YouTube Music', 'Media content; never an opportunity source.'),
]

def seed_blacklist(apps, schema_editor):
    B=apps.get_model('portal','SourceBlacklist')
    for domain,label,reason in DEFAULT_BLACKLIST:
        B.objects.get_or_create(domain=domain, defaults={'label':label,'reason':reason,'built_in':True,'enabled':True})
    Opportunity=apps.get_model('portal','Opportunity')
    for o in Opportunity.objects.all().iterator():
        changed=[]
        if not getattr(o,'target_url',''):
            o.target_url=o.url or ''; changed.append('target_url')
        if not getattr(o,'search_url',''):
            o.search_url=o.url or ''; changed.append('search_url')
        if changed: o.save(update_fields=changed)
    CompanyLead=apps.get_model('portal','CompanyLead')
    for x in CompanyLead.objects.all().iterator():
        changed=[]
        if not getattr(x,'target_url',''):
            x.target_url=x.source_url or ''; changed.append('target_url')
        if not getattr(x,'search_url',''):
            x.search_url=x.source_url or ''; changed.append('search_url')
        if changed: x.save(update_fields=changed)

def unseed(apps, schema_editor):
    B=apps.get_model('portal','SourceBlacklist')
    B.objects.filter(built_in=True).delete()

class Migration(migrations.Migration):
    dependencies=[('portal','0004_v082_ui_mail_resources')]
    operations=[
        migrations.AddField(model_name='portalsettings',name='last_hidden_scan',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='opportunity',name='search_url',field=models.URLField(blank=True,help_text='URL originally returned by the search provider.',max_length=1000)),
        migrations.AddField(model_name='opportunity',name='target_url',field=models.URLField(blank=True,help_text='Resolved/fetched destination URL used for analysis.',max_length=1000)),
        migrations.AddField(model_name='opportunity',name='language_code',field=models.CharField(blank=True,default='',max_length=16)),
        migrations.AddField(model_name='companylead',name='search_url',field=models.URLField(blank=True,max_length=1000)),
        migrations.AddField(model_name='companylead',name='target_url',field=models.URLField(blank=True,max_length=1000)),
        migrations.AddField(model_name='companylead',name='language_code',field=models.CharField(blank=True,default='',max_length=16)),
        migrations.AddField(model_name='aiproviderconfig',name='max_output_tokens',field=models.PositiveIntegerField(blank=True,help_text='Cloud-provider output cap. Local Ollama has no provider billing cap.',null=True)),
        migrations.CreateModel(name='SourceBlacklist',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('domain',models.CharField(max_length=255,unique=True)),
            ('label',models.CharField(blank=True,max_length=255)),
            ('reason',models.CharField(blank=True,max_length=500)),
            ('enabled',models.BooleanField(default=True)),
            ('built_in',models.BooleanField(default=False)),
            ('created_at',models.DateTimeField(auto_now_add=True)),
        ],options={'ordering':['domain']}),
        migrations.RunPython(seed_blacklist,unseed),
    ]
