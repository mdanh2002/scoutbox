from django.db import migrations


OLD_DEFAULT_MARKETS=['worldwide','us','ca','gb','ie','au','nz','sg','my','hk','in','ph','ae','za','mt']
NEW_MARKETS=['de','fr','es','pt','nl','it','pl','cz','dk','se','no','fi','jp','kr','br','mx']

SOURCES={
    'StepStone Germany':('https://www.stepstone.de','de'),
    'France Travail':('https://www.francetravail.fr','fr'),
    'InfoJobs Spain':('https://www.infojobs.net','es'),
    'Net-Empregos Portugal':('https://www.net-empregos.com','pt'),
    'Nationale Vacaturebank':('https://www.nationalevacaturebank.nl','nl'),
    'Cliclavoro Italy':('https://www.cliclavoro.gov.it','it'),
    'Pracuj.pl':('https://www.pracuj.pl','pl'),
    'Jobs.cz':('https://www.jobs.cz','cz'),
    'Jobindex Denmark':('https://www.jobindex.dk','dk'),
    'Arbetsförmedlingen Platsbanken':('https://arbetsformedlingen.se/platsbanken','se'),
    'FINN Jobs':('https://www.finn.no/job/search','no'),
    'Jobly Finland':('https://www.jobly.fi','fi'),
    'Daijob':('https://www.daijob.com','jp'),
    'JobKorea':('https://www.jobkorea.co.kr','kr'),
    'Vagas.com.br':('https://www.vagas.com.br','br'),
    'OCCMundial':('https://www.occ.com.mx','mx'),
}


def forward(apps, schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings')
    SearchSource=apps.get_model('portal','SearchSource')
    settings=PortalSettings.objects.filter(pk=1).first()
    if settings:
        current=list(settings.discovery_markets or [])
        if not current or set(current)==set(OLD_DEFAULT_MARKETS):
            settings.discovery_markets=list(dict.fromkeys((current or OLD_DEFAULT_MARKETS)+NEW_MARKETS))
            settings.save(update_fields=['discovery_markets'])
    for name,(url,market) in SOURCES.items():
        row,created=SearchSource.objects.get_or_create(name=name,defaults={
            'category':'Major job sites','source_type':'job_site','base_url':url,
            'enabled':True,'priority':50,'adapter_status':'preset',
            'requires_credentials':False,'public_fallback':False,'config_json':{},
        })
        config=dict(row.config_json or {})
        config.update({'market_specific':True,'market_codes':[market],'discovery_capability':'Market-specific site search · search engine'})
        row.category='Major job sites'; row.source_type='job_site'; row.base_url=url; row.config_json=config
        row.save(update_fields=['category','source_type','base_url','config_json'])


def backward(apps, schema_editor):
    # Preserve source rows and operator selections on downgrade.
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0154_v01175_discovery_markets_ui_refine')]
    operations=[migrations.RunPython(forward,backward)]
