from django.db import migrations


def forwards(apps, schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings')
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    Contact=apps.get_model('portal','Contact')
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    try:
        from django.utils import timezone
        now=timezone.now()
        BackgroundJob.objects.filter(status__in=['queued','running']).filter(label__icontains='Focus').update(
            status='stopped',message='Superseded by ScoutBox 0.10.110 residual Focus repair',finished_at=now
        )
    except Exception:
        pass
    results={}
    try:
        from portal.services.focus import repair_model_focus_taxonomy
        target=int(getattr(ps,'max_focus_groups',15) or 15)
        results={
            'opportunities':repair_model_focus_taxonomy(Opportunity,target,rewrite=True),
            'hidden_leads':repair_model_focus_taxonomy(CompanyLead,target,rewrite=True),
            'address_book':repair_model_focus_taxonomy(Contact,target,rewrite=True),
        }
    except Exception as exc:
        results={'error':str(exc)[:500]}
    state=dict(ps.focus_taxonomy_state or {})
    state['focus_residual_release']='0.10.110'
    state['focus_residual_repair']=results
    state['focus_target_unclassified_ratio']='10-15% when supported by content'
    state['hide_failed_urls_footer_left']=True
    ps.focus_taxonomy_state=state
    ps.focus_taxonomy_version='0.10.110'
    ps.save(update_fields=['focus_taxonomy_state','focus_taxonomy_version'])


class Migration(migrations.Migration):
    dependencies=[('portal','0129_v010109_focus_company_ui_repair')]
    operations=[migrations.RunPython(forwards, migrations.RunPython.noop)]
