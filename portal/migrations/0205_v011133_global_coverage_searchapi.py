from django.db import migrations, models
import urllib.parse


def forwards(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    AuditLog = apps.get_model('portal', 'AuditLog')

    SearchSource.objects.update_or_create(
        name='SearchAPI · Google Jobs',
        defaults={
            'category':'Search APIs / SERP',
            'source_type':'search_api',
            'base_url':'https://www.searchapi.io/',
            'enabled':True,
            'preferred_initial':True,
            'priority':98,
            'provider_weight':145,
            'requires_credentials':True,
            'adapter_status':'active',
            'notes':'Market-localized Google Jobs discovery through SearchAPI. ScoutBox always sends an explicit Discovery Market so Google cannot silently fall back to US geography.',
            'config_json':{
                'discovery_capability':'Localized structured Google Jobs acquisition',
                'shared_credential_group':'searchapi',
                'market_aware':True,
            },
            'public_fallback':False,
        },
    )
    SearchSource.objects.update_or_create(
        name='SearchAPI · Google Web',
        defaults={
            'category':'Search APIs / SERP',
            'source_type':'search_api',
            'base_url':'https://www.searchapi.io/',
            'enabled':True,
            'preferred_initial':True,
            'priority':96,
            'provider_weight':135,
            'requires_credentials':True,
            'adapter_status':'active',
            'notes':'Market-localized Google web discovery through SearchAPI for regional job boards, employer pages and ATS/source discovery.',
            'config_json':{
                'discovery_capability':'Localized Google Web / local-board discovery',
                'shared_credential_group':'searchapi',
                'market_aware':True,
            },
            'public_fallback':False,
        },
    )


    # Repair only high-confidence legacy false-US/blank countries where the opportunity
    # URL itself belongs to a country-specific job-board domain. Previous broad page
    # inference could read US corporate/footer text and overwrite an obvious local board.
    Opportunity = apps.get_model('portal', 'Opportunity')
    domain_countries = {
        'hk.jobsdb.com':'Hong Kong',
        'sg.jobstreet.com':'Singapore', 'my.jobstreet.com':'Malaysia', 'ph.jobstreet.com':'Philippines',
        'seek.com.au':'Australia', 'seek.co.nz':'New Zealand', 'reed.co.uk':'United Kingdom',
        'mycareersfuture.gov.sg':'Singapore', 'jobbank.gc.ca':'Canada', 'irishjobs.ie':'Ireland',
        'careers24.com':'South Africa',
        'stepstone.de':'Germany', 'francetravail.fr':'France',
        'infojobs.net':'Spain', 'net-empregos.com':'Portugal',
        'nationalevacaturebank.nl':'Netherlands',
        'pracuj.pl':'Poland', 'jobs.cz':'Czechia',
        'jobindex.dk':'Denmark', 'jobly.fi':'Finland',
        'jobkorea.co.kr':'South Korea',
        'vagas.com.br':'Brazil', 'occ.com.mx':'Mexico',
    }
    for opportunity in Opportunity.objects.all().iterator():
        if str(getattr(opportunity, 'country', '') or '').strip() not in {'', 'United States'}:
            continue
        host=''
        primary_urls=[getattr(opportunity,'target_url',''), getattr(opportunity,'url','')]
        # Search URL is discovery provenance and may point at a regional board even when the
        # final employer role is elsewhere. Use it only when no concrete target/url exists.
        values=primary_urls if any(str(x or '').strip() for x in primary_urls) else [getattr(opportunity,'search_url','')]
        for value in values:
            try:
                candidate=(urllib.parse.urlsplit(str(value or '')).hostname or '').lower().removeprefix('www.')
            except Exception:
                candidate=''
            if candidate in domain_countries:
                host=candidate
                break
        country=domain_countries.get(host)
        if not country:
            continue
        facts=dict(getattr(opportunity,'extracted_facts',{}) or {})
        evidence=f'Country-specific source domain: {host}'
        facts['country_provenance']={
            'source':'legacy_local_board_market_repair', 'evidence':evidence, 'fallback':True,
            'policy':'0.11.133 country-specific source-domain repair for legacy blank/false-US records',
        }
        opportunity.country=country
        opportunity.locations=[{
            'kind':'country','label':country,'code':country,'icon':'',
            'source':'legacy_local_board_market_repair','evidence':evidence,
        }]
        opportunity.extracted_facts=facts
        opportunity.save(update_fields=['country','locations','extracted_facts','updated_at'])

    # Install the expanded world catalogue only for installations that were still using
    # the previous all-markets set. Deliberately customized subsets remain untouched.
    legacy_default_codes = ['worldwide', 'us', 'ca', 'gb', 'ie', 'au', 'nz', 'sg', 'my', 'hk', 'in', 'ph', 'ae', 'za', 'mt', 'de', 'fr', 'es', 'pt', 'nl', 'it', 'pl', 'cz', 'dk', 'se', 'no', 'fi', 'jp', 'kr', 'br', 'mx']
    expanded_default_codes = ['worldwide', 'us', 'ca', 'gb', 'ie', 'au', 'nz', 'sg', 'my', 'hk', 'in', 'ph', 'ae', 'za', 'mt', 'de', 'fr', 'es', 'pt', 'nl', 'it', 'pl', 'cz', 'dk', 'se', 'no', 'fi', 'jp', 'kr', 'br', 'mx', 'af', 'al', 'dz', 'ad', 'ao', 'ag', 'ar', 'am', 'at', 'az', 'bs', 'bh', 'bd', 'bb', 'by', 'be', 'bz', 'bj', 'bt', 'bo', 'ba', 'bw', 'bn', 'bg', 'bf', 'bi', 'kh', 'cm', 'cv', 'cf', 'td', 'cl', 'cn', 'co', 'km', 'cr', 'hr', 'cu', 'cy', 'cd', 'dj', 'dm', 'do', 'ec', 'eg', 'sv', 'gq', 'er', 'ee', 'sz', 'et', 'fj', 'ga', 'gm', 'ge', 'gh', 'gr', 'gd', 'gt', 'gn', 'gw', 'gy', 'ht', 'hn', 'hu', 'is', 'id', 'ir', 'iq', 'il', 'ci', 'jm', 'jo', 'kz', 'ke', 'ki', 'kw', 'kg', 'la', 'lv', 'lb', 'ls', 'lr', 'ly', 'li', 'lt', 'lu', 'mg', 'mw', 'mv', 'ml', 'mh', 'mr', 'mu', 'fm', 'md', 'mc', 'mn', 'me', 'ma', 'mz', 'mm', 'na', 'nr', 'np', 'ni', 'ne', 'ng', 'kp', 'mk', 'om', 'pk', 'pw', 'ps', 'pa', 'pg', 'py', 'pe', 'qa', 'cg', 'ro', 'ru', 'rw', 'kn', 'lc', 'vc', 'ws', 'sm', 'st', 'sa', 'sn', 'rs', 'sc', 'sl', 'sk', 'si', 'sb', 'so', 'ss', 'lk', 'sd', 'sr', 'ch', 'sy', 'tw', 'tj', 'tz', 'th', 'tl', 'tg', 'to', 'tt', 'tn', 'tr', 'tm', 'tv', 'ug', 'ua', 'uy', 'uz', 'vu', 'va', 've', 'vn', 'ye', 'zm', 'zw']
    legacy_set=set(legacy_default_codes)
    for settings_row in PortalSettings.objects.all().iterator():
        current=[str(x).lower() for x in (getattr(settings_row,'discovery_markets',[]) or []) if str(x).strip()]
        if current and legacy_set.issubset(set(current)):
            settings_row.discovery_markets=list(expanded_default_codes)
            settings_row.save(update_fields=['discovery_markets','updated_at'])

    # Preserve explicit Adaptive/Even choices. Balanced was the previous default and is
    # upgraded to the new acquisition-fair strategy so existing installations benefit.
    PortalSettings.objects.filter(discovery_market_strategy='balanced').update(discovery_market_strategy='global')

    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.133').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.133',
            summary='ScoutBox upgraded to version 0.11.133.',
            metadata={
                'release':'0.11.133',
                'global_coverage':True,
                'searchapi_google_jobs':True,
                'searchapi_google_web':True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0204_v011132_reevaluation_reliability')]
    operations = [
        migrations.AlterField(
            model_name='portalsettings',
            name='discovery_market_strategy',
            field=models.CharField(
                max_length=20,
                default='global',
                choices=[
                    ('global','Global Coverage'),
                    ('balanced','Balanced'),
                    ('adaptive','Adaptive'),
                    ('even','Even'),
                ],
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
