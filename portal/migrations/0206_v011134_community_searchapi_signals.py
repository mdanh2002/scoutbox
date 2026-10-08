from django.db import migrations


def forwards(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    AuditLog = apps.get_model('portal', 'AuditLog')

    # Keep every SearchAPI engine together on the Sources screen. They share one API key
    # and, as of 0.11.134, one daily credit/request budget rather than multiplying the same
    # account allowance by the number of engines.
    SearchSource.objects.filter(name__in=['SearchAPI · Google Jobs', 'SearchAPI · Google Web']).update(
        category='SearchAPI Discovery'
    )

    SearchSource.objects.update_or_create(
        name='SearchAPI · Google Forums',
        defaults={
            'category':'SearchAPI Discovery',
            'source_type':'search_api',
            'base_url':'https://www.searchapi.io/',
            'enabled':True,
            'preferred_initial':False,
            'priority':92,
            'provider_weight':105,
            'requires_credentials':True,
            'adapter_status':'active',
            'notes':'Supplemental, market-localized Google Forums discovery through SearchAPI. Finds current Reddit, Stack Exchange, vendor-forum and niche-community hiring signals without depending on the native Reddit endpoint. Signals normally become Hidden Leads unless the underlying page is independently verified as a concrete vacancy.',
            'config_json':{
                'discovery_capability':'Localized forum/community hiring-signal discovery',
                'shared_credential_group':'searchapi',
                'shared_budget_group':'searchapi',
                'market_aware':True,
                'supplemental_only':True,
                'signal_mode':'community',
            },
            'public_fallback':False,
        },
    )
    SearchSource.objects.update_or_create(
        name='SearchAPI · Google News',
        defaults={
            'category':'SearchAPI Discovery',
            'source_type':'search_api',
            'base_url':'https://www.searchapi.io/',
            'enabled':True,
            'preferred_initial':False,
            'priority':90,
            'provider_weight':95,
            'requires_credentials':True,
            'adapter_status':'active',
            'notes':'Supplemental, market-localized Google News discovery through SearchAPI. Recent hiring, expansion and project signals are evidence for Hidden Leads only; a news article is never treated as a vacancy URL.',
            'config_json':{
                'discovery_capability':'Localized recent company hiring/expansion signals',
                'shared_credential_group':'searchapi',
                'shared_budget_group':'searchapi',
                'market_aware':True,
                'supplemental_only':True,
                'signal_mode':'news',
            },
            'public_fallback':False,
        },
    )

    # Add shared-budget metadata to the two existing SearchAPI engines without replacing
    # operator credentials or other per-source configuration created by 0.11.133.
    for source in SearchSource.objects.filter(name__in=['SearchAPI · Google Jobs', 'SearchAPI · Google Web']):
        cfg=dict(source.config_json or {})
        cfg['shared_credential_group']='searchapi'
        cfg['shared_budget_group']='searchapi'
        cfg['market_aware']=True
        source.config_json=cfg
        source.save(update_fields=['config_json'])

    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.134').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.134',
            summary='ScoutBox upgraded to version 0.11.134.',
            metadata={
                'release':'0.11.134',
                'community_hiring_signals':True,
                'cloud_community_signal_qualification':True,
                'searchapi_google_forums':True,
                'searchapi_google_news':True,
                'searchapi_shared_budget':True,
                'reddit_searchapi_fallback':True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0205_v011133_global_coverage_searchapi')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
