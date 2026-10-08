from django.db import migrations, models

DEFAULT_MARKETS=['worldwide','us','ca','gb','ie','au','nz','sg','my','hk','in','ph','ae','za','mt']
OLD_HIGH='Embedded systems, reverse engineering, retro computing, QEMU/virtualization, legacy systems and rare specialist roles.'
OLD_MED='Technical writing, remote teaching/training, consulting and adjacent low-level tooling with concrete fit and a short process.'
OLD_LOW='Interesting adjacent OSS/support or unusual software work. Avoid low-rate marketplaces and clearly unsuitable engagement models.'
SOURCES={
 'SEEK Australia':('Major job sites','https://www.seek.com.au','au'),
 'SEEK New Zealand':('Major job sites','https://www.seek.co.nz','nz'),
 'MyCareersFuture':('Major job sites','https://www.mycareersfuture.gov.sg','sg'),
 'JobStreet Singapore':('Major job sites','https://sg.jobstreet.com','sg'),
 'JobStreet Malaysia':('Major job sites','https://my.jobstreet.com','my'),
 'JobsDB Hong Kong':('Major job sites','https://hk.jobsdb.com','hk'),
 'JobStreet Philippines':('Major job sites','https://ph.jobstreet.com','ph'),
 'Reed UK':('Major job sites','https://www.reed.co.uk','gb'),
 'IrishJobs':('Major job sites','https://www.irishjobs.ie','ie'),
 'Job Bank Canada':('Major job sites','https://www.jobbank.gc.ca','ca'),
 'GulfTalent':('Major job sites','https://www.gulftalent.com','ae'),
 'Careers24':('Major job sites','https://www.careers24.com','za'),
}

def forward(apps,schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings'); Profile=apps.get_model('portal','Profile'); SearchSource=apps.get_model('portal','SearchSource')
    cfg=PortalSettings.objects.filter(pk=1).first()
    if cfg and not cfg.discovery_markets:
        cfg.discovery_markets=DEFAULT_MARKETS; cfg.save(update_fields=['discovery_markets'])
    p=Profile.objects.filter(pk=1).first()
    if p:
        changed=[]
        if p.high_priority_text==OLD_HIGH: p.high_priority_text=''; changed.append('high_priority_text')
        if p.medium_priority_text==OLD_MED: p.medium_priority_text=''; changed.append('medium_priority_text')
        if p.low_priority_text==OLD_LOW: p.low_priority_text=''; changed.append('low_priority_text')
        if changed: p.save(update_fields=changed)
    # Preferred Search Engines is retired: every enabled engine is eligible.
    SearchSource.objects.filter(source_type__in=['search_engine','regional_search']).update(preferred_initial=True)
    for name,(category,url,market) in SOURCES.items():
        row,_=SearchSource.objects.get_or_create(name=name,defaults={'category':category,'source_type':'job_site','base_url':url,'enabled':True,'priority':50,'adapter_status':'preset','requires_credentials':False,'public_fallback':False,'config_json':{}})
        cfgj=dict(row.config_json or {}); cfgj.update({'market_specific':True,'market_codes':[market],'discovery_capability':'Market-specific site search · search engine'})
        row.category=category; row.source_type='job_site'; row.base_url=url; row.config_json=cfgj
        row.save(update_fields=['category','source_type','base_url','config_json'])

def backward(apps,schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies=[('portal','0152_v01171_external_stats_default')]
    operations=[
      migrations.AddField(model_name='portalsettings',name='discovery_markets',field=models.JSONField(blank=True,default=list,help_text='Enabled acquisition markets. Empty legacy values are interpreted as all supported markets.')),
      migrations.AddField(model_name='portalsettings',name='discovery_market_strategy',field=models.CharField(choices=[('balanced','Balanced'),('adaptive','Adaptive'),('even','Even')],default='balanced',max_length=20)),
      migrations.AddField(model_name='portalsettings',name='multilingual_exploration_enabled',field=models.BooleanField(default=False)),
      migrations.AddField(model_name='portalsettings',name='multilingual_language_mode',field=models.CharField(choices=[('auto','Auto'),('custom','Custom')],default='auto',max_length=12)),
      migrations.AddField(model_name='portalsettings',name='multilingual_languages',field=models.JSONField(blank=True,default=list)),
      migrations.AddField(model_name='portalsettings',name='multilingual_exploration_strength',field=models.CharField(choices=[('low','Low'),('balanced','Balanced'),('high','High')],default='balanced',max_length=12)),
      migrations.AlterField(model_name='profile',name='high_priority_text',field=models.TextField(blank=True,default='')),
      migrations.AlterField(model_name='profile',name='medium_priority_text',field=models.TextField(blank=True,default='')),
      migrations.AlterField(model_name='profile',name='low_priority_text',field=models.TextField(blank=True,default='')),
      migrations.RunPython(forward,backward),
    ]
