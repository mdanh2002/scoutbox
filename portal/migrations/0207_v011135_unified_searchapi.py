from django.db import migrations, models


def forwards(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    AuditLog = apps.get_model('portal', 'AuditLog')

    existing_names=['SearchAPI · Google Jobs','SearchAPI · Google Web','SearchAPI · Google Forums','SearchAPI · Google News']
    for source in SearchSource.objects.filter(name__in=existing_names):
        cfg=dict(source.config_json or {})
        cfg.setdefault('auto_enabled', bool(source.enabled))
        cfg['shared_credential_group']='searchapi'
        cfg['shared_budget_group']='searchapi'
        cfg['market_aware']=True
        source.category='Search APIs / SERP'
        source.config_json=cfg
        source.save(update_fields=['category','config_json'])

    defaults={
        'SearchAPI · ChatGPT Research': {
            'source_type':'searchapi_research','priority':70,'provider_weight':60,
            'notes':'Optional, sparse AI-assisted public-web research with citations. Used only for difficult current-web verification/rescue tasks and logged under AI Requests / Cloud Runtime; direct OpenAI/Gemini/OpenRouter remains preferred.',
            'config_json':{'discovery_capability':'Sparse cited public-web research','shared_credential_group':'searchapi','shared_budget_group':'searchapi','supplemental_only':True,'auto_enabled':False,'auto_daily_limit':10,'research_only':True},
        },
        'SearchAPI · Google AI Mode': {
            'source_type':'search_api','priority':68,'provider_weight':55,
            'notes':'Optional SearchAPI Google AI Mode research. Supplemental only, market-localized and logged as Search Activity rather than a direct ScoutBox AI-provider request.',
            'config_json':{'discovery_capability':'Sparse market-localized AI web research','shared_credential_group':'searchapi','shared_budget_group':'searchapi','market_aware':True,'supplemental_only':True,'auto_enabled':False,'auto_daily_limit':10,'research_only':True},
        },
        'SearchAPI · Google Local': {
            'source_type':'search_api','priority':66,'provider_weight':50,
            'notes':'Optional employer/business discovery for under-covered markets. Results are leads for further company/careers/hiring verification, never direct vacancies by themselves.',
            'config_json':{'discovery_capability':'Localized employer/business discovery','shared_credential_group':'searchapi','shared_budget_group':'searchapi','market_aware':True,'supplemental_only':True,'auto_enabled':False,'signal_mode':'employer_discovery'},
        },
    }
    for name, spec in defaults.items():
        SearchSource.objects.update_or_create(name=name, defaults={
            'category':'Search APIs / SERP','base_url':'https://www.searchapi.io/','enabled':False,
            'preferred_initial':False,'requires_credentials':True,'adapter_status':'active','public_fallback':False,
            **spec,
        })

    hub=SearchSource.objects.filter(name='SearchAPI · Google Jobs').first()
    if hub:
        cfg=dict(hub.config_json or {})
        cfg.setdefault('searchapi_master_enabled', bool(hub.enabled))
        hub.config_json=cfg; hub.save(update_fields=['config_json'])

    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.135').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.135', summary='ScoutBox upgraded to version 0.11.135.',
            metadata={
                'release':'0.11.135','unified_searchapi_ui':True,'searchapi_chatgpt_research':True,
                'searchapi_google_ai_mode':True,'searchapi_google_local':True,'searchapi_shared_daily_limit':500,
                'searchapi_chatgpt_ai_request_logging':True,'quota_pressure_gauges':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0206_v011134_community_searchapi_signals')]
    operations=[
        migrations.AddField(
            model_name='portalsettings', name='searchapi_daily_limit',
            field=models.PositiveIntegerField(default=500, help_text='Shared daily request cap across all SearchAPI services; 0 disables automatic/manual SearchAPI requests without removing credentials.'),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
