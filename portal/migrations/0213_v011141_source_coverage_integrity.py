from django.db import migrations


def forwards(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    AuditLog=apps.get_model('portal','AuditLog')

    source,created=SearchSource.objects.get_or_create(
        name='YC Work at a Startup',
        defaults={
            'category':'Startup / technology jobs',
            'source_type':'job_site',
            'base_url':'https://www.workatastartup.com/jobs',
            'enabled':True,
            'priority':50,
            'provider_weight':100,
            'requires_credentials':False,
            'adapter_status':'direct',
            'public_fallback':True,
            'config_json':{},
        },
    )
    cfg=dict(getattr(source,'config_json',{}) or {})
    cfg.update({
        'direct_adapter':'yc_jobs',
        'direct_capability':'YC Jobs direct pages',
        'discovery_capability':'YC Jobs direct pages · Local + search engine · Cloud direct only',
    })
    source.config_json=cfg
    source.adapter_status='direct'
    update_fields=['config_json','adapter_status']
    if not str(getattr(source,'base_url','') or '').strip():
        source.base_url='https://www.workatastartup.com/jobs'; update_fields.append('base_url')
    if not str(getattr(source,'category','') or '').strip():
        source.category='Startup / technology jobs'; update_fields.append('category')
    if not str(getattr(source,'source_type','') or '').strip():
        source.source_type='job_site'; update_fields.append('source_type')
    source.save(update_fields=update_fields)

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.141').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.141',summary='ScoutBox upgraded to version 0.11.141.',
            metadata={
                'release':'0.11.141',
                'source_coverage_integrity':True,
                'bounded_source_rotation':True,
                'direct_source_exploration_slots':True,
                'yc_jobs_direct_adapter':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0212_v011140_facebook_page_identity_titles')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
