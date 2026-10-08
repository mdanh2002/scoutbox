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
        changed = False

        # Preserve pre-access-type Naver credentials in the legacy credential slot before
        # making Public Access the explicit default. Nothing is deleted or decrypted.
        if source.name == 'Naver' and (source.api_key_enc or cfg.get('api_extra')):
            slots = dict(cfg.get('access_credentials') or {})
            legacy = dict(slots.get('naver_legacy') or {})
            if source.api_key_enc and not legacy.get('secret_enc'):
                legacy['secret_enc'] = source.api_key_enc
                changed = True
            if cfg.get('api_extra') and not legacy.get('extra'):
                legacy['extra'] = cfg.get('api_extra')
                changed = True
            slots['naver_legacy'] = legacy
            cfg['access_credentials'] = slots

        selected = str(cfg.get('access_type') or '').strip()
        if selected not in VALID_ACCESS[source.name]:
            cfg['access_type'] = 'public'
            changed = True

        if changed:
            source.config_json = cfg
            source.save(update_fields=['config_json'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0017_v0820_search_market_quality')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
