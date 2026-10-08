from django.db import migrations


CAPABILITIES = {
    'LinkedIn Jobs':'Job Library API when configured · Local + search engine · Cloud direct only',
    'Glassdoor':'Jobs API when configured · Local + search engine · Cloud direct only',
    'Indeed':'Partner-only direct search · Local search engine · Cloud native web',
    'ZipRecruiter':'Local search engine · Cloud native web',
    'Dice':'Local search engine · Cloud native web',
    'Monster':'Local search engine · Cloud native web',
    'Wellfound':'Direct page · Local + search engine · Cloud direct only',
    'Remote OK':'Direct job API · Local + search engine · Cloud direct only',
    'Remotive':'Direct job API · Local + search engine · Cloud direct only',
    'Himalayas':'Direct job API · Local + search engine · Cloud direct only',
    'Jobicy':'Direct job API · Local + search engine · Cloud direct only',
    'We Work Remotely':'Official RSS/feed · Local + search engine · Cloud direct only',
    'Hacker News Who is Hiring':'Community API · Local + search engine · Cloud direct only',
    'Lobsters':'Community RSS · Local + search engine · Cloud direct only',
    'DEV Community Hiring':'Community API · Local + search engine · Cloud direct only',
    'Indie Hackers Jobs':'Direct page · Local + search engine · Cloud direct only',
    'Reddit':'Community API · Local + search engine · Cloud direct only',
    'Greenhouse':'ATS API · Local + search engine · Cloud direct only',
    'Lever':'ATS API · Local + search engine · Cloud direct only',
    'Ashby':'ATS API · Local + search engine · Cloud direct only',
    'SmartRecruiters':'ATS API · Local + search engine · Cloud direct only',
}


def forward(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    for name, capability in CAPABILITIES.items():
        row=SearchSource.objects.filter(name=name).first()
        if not row:
            continue
        cfg=dict(row.config_json or {})
        cfg['discovery_capability']=capability
        row.config_json=cfg
        row.save(update_fields=['config_json'])


def backward(apps, schema_editor):
    # Preserve operator-customized capability metadata on downgrade.
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0087_v01033_discovery_performance_sources')]
    operations=[migrations.RunPython(forward,backward)]
