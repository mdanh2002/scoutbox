from django.db import migrations


def forwards(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    AuditLog=apps.get_model('portal','AuditLog')

    # Raise only the historical 0.11.135 defaults. If the user deliberately set a
    # different custom value, preserve it.
    for name in ('SearchAPI · ChatGPT Research','SearchAPI · Google AI Mode'):
        source=SearchSource.objects.filter(name=name).first()
        if not source:
            continue
        cfg=dict(source.config_json or {})
        old=cfg.get('auto_daily_limit')
        if old in (None,10,'10'):
            cfg['auto_daily_limit']=100
            source.config_json=cfg
            source.save(update_fields=['config_json'])

    hub=SearchSource.objects.filter(name='SearchAPI · Google Jobs').first()
    if hub:
        cfg=dict(hub.config_json or {})
        # Existing installations with a credential predate save-time validation. Do not
        # mislabel them as failed; the next Save API key action performs the sanity check.
        cfg.setdefault('searchapi_validation_status','')
        cfg.setdefault('searchapi_validation_message','')
        hub.config_json=cfg
        hub.save(update_fields=['config_json'])

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.137').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.137',summary='ScoutBox upgraded to version 0.11.137.',
            metadata={
                'release':'0.11.137',
                'searchapi_save_validation':True,
                'searchapi_validation_warning_state':True,
                'searchapi_service_grid':True,
                'searchapi_compact_test_results':True,
                'searchapi_ai_auto_default':100,
                'search_activity_vertical_alignment':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0208_v011136_searchapi_ui_cleanup')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
