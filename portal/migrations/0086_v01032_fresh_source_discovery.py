from django.db import migrations

DIRECT = {
    'Remote OK': ('Remote-focused boards','job_site','https://remoteok.com','remoteok','Direct job API'),
    'Remotive': ('Remote-focused boards','job_site','https://remotive.com','remotive','Direct job API'),
    'Himalayas': ('Remote-focused boards','job_site','https://himalayas.app','himalayas','Direct job API'),
    'Jobicy': ('Remote-focused boards','job_site','https://jobicy.com','jobicy','Direct job API'),
    'We Work Remotely': ('Remote-focused boards','job_site','https://weworkremotely.com','wwr_rss','RSS / feed'),
    'Hacker News Who is Hiring': ('Fresh job feeds / communities','community','https://news.ycombinator.com','hn_whoishiring','Community API'),
    'Reddit': ('Public community / social sources','social','https://www.reddit.com','reddit','Reddit API'),
    'Greenhouse': ('ATS / hosted career pages','ats','https://www.greenhouse.com','greenhouse','ATS API · learned employer boards'),
    'Lever': ('ATS / hosted career pages','ats','https://www.lever.co','lever','ATS API · learned employer boards'),
    'Ashby': ('ATS / hosted career pages','ats','https://www.ashbyhq.com','ashby','ATS API · learned employer boards'),
    'SmartRecruiters': ('ATS / hosted career pages','ats','https://www.smartrecruiters.com','smartrecruiters','ATS API · learned employer boards'),
}


def forward(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    for name,(category,stype,url,adapter,capability) in DIRECT.items():
        row,_=SearchSource.objects.get_or_create(name=name,defaults={
            'category':category,'source_type':stype,'base_url':url,'enabled':True,
            'priority':50,'adapter_status':'direct','requires_credentials':False,
            'public_fallback':False,'config_json':{},
        })
        cfg=dict(row.config_json or {})
        cfg.update({'direct_adapter':adapter,'direct_capability':capability})
        if name=='Reddit':
            cfg.update({'oauth_client_id_env':'REDDIT_CLIENT_ID','oauth_client_secret_env':'REDDIT_CLIENT_SECRET','user_agent_env':'REDDIT_USER_AGENT'})
        row.category=category; row.source_type=stype; row.base_url=url
        row.adapter_status='direct'; row.config_json=cfg
        row.save(update_fields=['category','source_type','base_url','adapter_status','config_json'])


def backward(apps, schema_editor):
    # Capability metadata is harmless on downgrade and may be operator-customized.
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0085_v01031_naver_role_title_repair')]
    operations=[migrations.RunPython(forward,backward)]
