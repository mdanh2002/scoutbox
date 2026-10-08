from collections import defaultdict
from django.db import migrations


_FALSE_CREDENTIAL_ERRORS=(
    'searchapi api key is not configured',
    'searchapi is not configured',
)


def _is_false_unconfigured_attempt(text):
    value=str(text or '').casefold()
    return any(marker in value for marker in _FALSE_CREDENTIAL_ERRORS)


def forwards(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    SearchProviderStat=apps.get_model('portal','SearchProviderStat')
    UsageMetric=apps.get_model('portal','UsageMetric')
    AIRequestLog=apps.get_model('portal','AIRequestLog')
    AuditLog=apps.get_model('portal','AuditLog')

    # 0.11.135 could persist a Search Activity/AI Requests row even though SearchAPI had
    # no credential and therefore made no external request. Those rows are false telemetry:
    # remove them and repair the daily provider counters they inflated.
    removed=defaultdict(int)
    names=list(SearchSource.objects.filter(name__startswith='SearchAPI ·').values_list('name',flat=True))
    for row in UsageMetric.objects.filter(provider__in=names,stage='query').iterator():
        meta=row.metadata if isinstance(row.metadata,dict) else {}
        if _is_false_unconfigured_attempt(meta.get('error') or meta.get('message')):
            removed[(row.provider,row.at.date())]+=max(1,int(row.requests or 0))
            row.delete()

    for row in AIRequestLog.objects.filter(provider='SearchAPI',runtime='cloud',stage='searchapi_research',ok=False).iterator():
        if _is_false_unconfigured_attempt(row.error):
            service=str((row.metadata or {}).get('searchapi_service') or 'chatgpt') if isinstance(row.metadata,dict) else 'chatgpt'
            name={
                'chatgpt':'SearchAPI · ChatGPT Research',
                'ai_mode':'SearchAPI · Google AI Mode',
            }.get(service,'SearchAPI · ChatGPT Research')
            removed[(name,row.at.date())]+=1
            row.delete()

    source_ids={name:pk for pk,name in SearchSource.objects.filter(name__in=names).values_list('pk','name')}
    for (name,day),count in removed.items():
        source_id=source_ids.get(name)
        if not source_id:
            continue
        stat=SearchProviderStat.objects.filter(source_id=source_id,day=day).first()
        if not stat:
            continue
        stat.requests=max(0,int(stat.requests or 0)-count)
        stat.errors=max(0,int(stat.errors or 0)-count)
        try:
            stat.quota_units=max(0,stat.quota_units-count)
        except Exception:
            pass
        if _is_false_unconfigured_attempt(stat.last_error):
            stat.last_error=''
        stat.save(update_fields=['requests','errors','quota_units','last_error'])

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.136').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.136',summary='ScoutBox upgraded to version 0.11.136.',
            metadata={
                'release':'0.11.136','searchapi_unconfigured_preflight':True,
                'searchapi_false_telemetry_cleanup':True,'searchapi_modal_vertical_scroll':True,
                'searchapi_save_button_left':True,'quota_hover_preserves_pressure_color':True,
                'searchapi_limit_compact_schedule_row':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0207_v011135_unified_searchapi')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
