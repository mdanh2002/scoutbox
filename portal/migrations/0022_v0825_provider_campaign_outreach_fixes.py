from django.db import migrations


ACTIVE = {'Google','Bing','DuckDuckGo','Brave Search','Yahoo Search','Mojeek','Startpage','Ecosia','Yandex','Baidu','Naver'}


def forwards(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    Application = apps.get_model('portal', 'Application')

    # Preserve explicit user source choices. Only expand the historical shipped default
    # (Google/Bing, or no preferred sources at all) to the new default: all active search
    # engines except Baidu.
    preferred = set(SearchSource.objects.filter(name__in=ACTIVE, preferred_initial=True).values_list('name', flat=True))
    if not preferred or preferred.issubset({'Google', 'Bing'}):
        SearchSource.objects.filter(name__in=ACTIVE).update(preferred_initial=True)
        SearchSource.objects.filter(name='Baidu').update(preferred_initial=False)

    # Re-normalize multi-access providers so old blank/invalid config cannot surface as an
    # empty Access Type. Credential slots are deliberately preserved.
    allowed = {
        'Yandex': {'public', 'yandex_api_key', 'yandex_iam'},
        'Baidu': {'public', 'baidu_qianfan'},
        'Naver': {'public', 'naver_legacy', 'naver_hub'},
    }
    for name, values in allowed.items():
        for source in SearchSource.objects.filter(name=name):
            cfg = dict(source.config_json or {})
            access = str(cfg.get('access_type') or '').strip()
            if access not in values:
                cfg['access_type'] = 'public'
                source.config_json = cfg
                source.save(update_fields=['config_json'])

    # v0.8.23 created some unified outreach Opportunities with a generic title before the
    # generated email subject was ready. Use an already-generated specific email subject
    # where possible so Applications & Outreach immediately shows useful context.
    generic = {'direct outreach', 'specialist support', 'opportunity', 'hello'}
    for app in Application.objects.select_related('opportunity').all().iterator():
        opp = app.opportunity
        facts = dict(getattr(opp, 'extracted_facts', {}) or {})
        if not facts.get('outreach'):
            continue
        subject = str(getattr(app, 'email_subject', '') or '').strip()
        title = str(getattr(opp, 'title', '') or '').strip()
        if subject and subject.lower() not in generic and (not title or title.lower() in generic or title.lower().startswith('direct outreach')):
            opp.title = subject[:300]
            opp.save(update_fields=['title', 'updated_at'])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('portal', '0021_v0824_ui_workflow_fixes')]
    operations = [migrations.RunPython(forwards, backwards)]
