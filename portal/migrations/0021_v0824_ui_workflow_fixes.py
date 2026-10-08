from django.db import migrations


def forwards(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    CampaignTemplate = apps.get_model('portal', 'CampaignTemplate')

    # Multi-access providers must never render with an indeterminate access type.
    for name in ('Yandex', 'Baidu', 'Naver'):
        for source in SearchSource.objects.filter(name=name):
            cfg = dict(source.config_json or {})
            access = str(cfg.get('access_type') or '').strip()
            allowed = {
                'Yandex': {'public', 'yandex_api_key', 'yandex_iam'},
                'Baidu': {'public', 'baidu_qianfan'},
                'Naver': {'public', 'naver_legacy', 'naver_hub'},
            }[name]
            if access not in allowed:
                cfg['access_type'] = 'public'
                source.config_json = cfg
                source.save(update_fields=['config_json'])

    # Old shipped templates were generic and are intentionally removed. User-created
    # templates remain untouched; Candidate Profile can now regenerate profile-specific ones.
    CampaignTemplate.objects.filter(built_in=True).delete()


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0020_v0823_unified_applications_summary_reset')]
    operations = [migrations.RunPython(forwards, backwards)]
