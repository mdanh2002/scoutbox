from django.db import migrations, models


SEARCH_ENGINES = {
    'Google': {'credential_env':'GOOGLE_SEARCH_API_KEY', 'cx_env':'GOOGLE_SEARCH_CX'},
    'Brave Search': {'credential_env':'BRAVE_SEARCH_API_KEY'},
    'Mojeek': {'credential_env':'MOJEEK_SEARCH_API_KEY'},
    'Naver': {'credential_env':'NAVER_SEARCH_CLIENT_SECRET', 'client_id_env':'NAVER_SEARCH_CLIENT_ID'},
    'Bing': {},
    'DuckDuckGo': {},
    'Yahoo Search': {},
    'Startpage': {},
    'Ecosia': {},
    'Yandex': {},
    'Baidu': {},
}



def upgrade_v081(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    # 0.8.1 makes the normal source set useful out of the box. Known low-value
    # marketplaces remain disabled, while all other shipped sources are selected.
    SearchSource.objects.filter(low_value_marketplace=False).update(enabled=True)
    SearchSource.objects.filter(low_value_marketplace=True).update(enabled=False)
    for name, extra in SEARCH_ENGINES.items():
        src = SearchSource.objects.filter(name=name).first()
        if not src:
            continue
        cfg = dict(src.config_json or {})
        cfg.update({k:v for k,v in extra.items() if v})
        src.adapter_status = 'active'
        src.public_fallback = True
        src.requires_credentials = False
        src.config_json = cfg
        src.save(update_fields=['adapter_status','public_fallback','requires_credentials','config_json'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0002_v080_workflow_ux')]
    operations = [
        migrations.AlterField(
            model_name='performancerun',
            name='kind',
            field=models.CharField(choices=[
                ('chat','Simple chat'), ('search','Search provider test'), ('scrape','Page scrape'),
                ('summarize','Summarize content'), ('extract','JD extraction'), ('rank','Opportunity ranking'),
                ('age_check','Job-post age analysis'), ('docx_to_pdf','DOCX to PDF conversion'),
            ], max_length=40),
        ),
        migrations.RunPython(upgrade_v081, migrations.RunPython.noop),
    ]
