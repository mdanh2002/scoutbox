from django.db import migrations


SOURCE_UPDATES = {
    'LinkedIn Jobs': {
        'category':'Major job sites','source_type':'job_site','base_url':'https://www.linkedin.com/jobs',
        'adapter_status':'direct','requires_credentials':True,
        'config':{'direct_adapter':'linkedin_job_library','direct_capability':'Job Library API · when configured','discovery_capability':'Job Library API when configured · search engine always','credential_env':'LINKEDIN_JOB_LIBRARY_ACCESS_TOKEN'},
    },
    'Indeed': {
        'category':'Major job sites','source_type':'job_site','base_url':'https://www.indeed.com',
        'config':{'discovery_capability':'Partner-only direct search · search engine always'},
    },
    'Glassdoor': {
        'category':'Major job sites','source_type':'job_site','base_url':'https://www.glassdoor.com',
        'adapter_status':'direct','requires_credentials':True,
        'config':{'direct_adapter':'glassdoor_jobs','direct_capability':'Jobs API · when explicitly configured','discovery_capability':'Jobs API when configured · search engine always','credential_env':'GLASSDOOR_API_KEY'},
    },
    'ZipRecruiter': {'category':'Major job sites','source_type':'job_site','base_url':'https://www.ziprecruiter.com','config':{'discovery_capability':'Search engine · always'}},
    'Dice': {'category':'Major job sites','source_type':'job_site','base_url':'https://www.dice.com','config':{'discovery_capability':'Search engine · always'}},
    'Monster': {'category':'Major job sites','source_type':'job_site','base_url':'https://www.monster.com','config':{'discovery_capability':'Search engine · always'}},
    'Wellfound': {
        'category':'Startup / technology jobs','source_type':'job_site','base_url':'https://wellfound.com/jobs','adapter_status':'direct',
        'config':{'direct_adapter':'wellfound_page','direct_capability':'Deterministic direct page','discovery_capability':'Direct page · search engine always'},
    },
    'Hacker News Who is Hiring': {
        'category':'Developer / engineering communities','source_type':'community','base_url':'https://news.ycombinator.com','adapter_status':'direct',
        'config':{'direct_adapter':'hn_whoishiring','direct_capability':'Community API','discovery_capability':'Community API · search engine always'},
    },
    'Lobsters': {
        'category':'Developer / engineering communities','source_type':'community','base_url':'https://lobste.rs','adapter_status':'direct',
        'config':{'direct_adapter':'lobsters_jobs','direct_capability':'Job-tag RSS','discovery_capability':'Community RSS · search engine always'},
    },
    'DEV Community Hiring': {
        'category':'Developer / engineering communities','source_type':'community','base_url':'https://dev.to/t/hiring','adapter_status':'direct',
        'config':{'direct_adapter':'dev_hiring','direct_capability':'Community API','discovery_capability':'Community API · search engine always'},
    },
    'Indie Hackers Jobs': {
        'category':'Developer / engineering communities','source_type':'community','base_url':'https://www.indiehackers.com/jobs','adapter_status':'direct',
        'config':{'direct_adapter':'indiehackers_jobs','direct_capability':'Deterministic direct page','discovery_capability':'Direct page · search engine always'},
    },
}

DIRECT_CAPABILITIES = {
    'Remote OK':'Direct job API · search engine always',
    'Remotive':'Direct job API · search engine always',
    'Himalayas':'Direct job API · search engine always',
    'Jobicy':'Direct job API · search engine always',
    'We Work Remotely':'Official RSS/feed · search engine always',
    'Reddit':'Community API · search engine always',
    'Greenhouse':'ATS API · search engine always',
    'Lever':'ATS API · search engine always',
    'Ashby':'ATS API · search engine always',
    'SmartRecruiters':'ATS API · search engine always',
}


def forward(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    for name, spec in SOURCE_UPDATES.items():
        defaults={
            'category':spec['category'],'source_type':spec['source_type'],'base_url':spec['base_url'],
            'enabled':True,'priority':50,'adapter_status':spec.get('adapter_status','preset'),
            'requires_credentials':bool(spec.get('requires_credentials',False)),'public_fallback':False,'config_json':{},
        }
        row,_=SearchSource.objects.get_or_create(name=name,defaults=defaults)
        cfg=dict(row.config_json or {}); cfg.update(spec.get('config') or {})
        row.category=spec['category']; row.source_type=spec['source_type']; row.base_url=spec['base_url']
        if spec.get('adapter_status'): row.adapter_status=spec['adapter_status']
        row.requires_credentials=bool(spec.get('requires_credentials',row.requires_credentials))
        row.config_json=cfg
        row.save(update_fields=['category','source_type','base_url','adapter_status','requires_credentials','config_json'])
    for name, capability in DIRECT_CAPABILITIES.items():
        row=SearchSource.objects.filter(name=name).first()
        if not row: continue
        cfg=dict(row.config_json or {}); cfg['discovery_capability']=capability
        row.config_json=cfg; row.save(update_fields=['config_json'])


def backward(apps, schema_editor):
    # Keep source capability metadata on downgrade; operators may have customized it.
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0086_v01032_fresh_source_discovery')]
    operations=[migrations.RunPython(forward,backward)]
