from django.db import migrations


VALID_ACCESS = {
    'Yandex': {'public', 'yandex_api_key', 'yandex_iam'},
    'Baidu': {'public', 'baidu_qianfan'},
    'Naver': {'public', 'naver_legacy', 'naver_hub'},
}


def forwards(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    for source in SearchSource.objects.filter(name__in=VALID_ACCESS):
        cfg = dict(source.config_json or {})
        selected = str(cfg.get('access_type') or '').strip()
        if selected not in VALID_ACCESS[source.name]:
            cfg['access_type'] = 'public'
            source.config_json = cfg
            source.save(update_fields=['config_json'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0018_v0821_access_defaults')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
