from django.db import migrations
from django.utils import timezone
from datetime import timedelta
import re

REMOTE_ROLE_LOCATION_RE=re.compile(r'(?i)\b(remote|hybrid|work\s+from\s+home|home[-\s]?based|telecommut|time\s*zone|timezone|overlap|working\s+hours|office\s+hours|cest|cet|est|pst|east\s+africa|west\s+africa)\b')


def repair_v010106_state(apps, schema_editor):
    BackgroundJob=apps.get_model('portal','BackgroundJob')
    PortalSettings=apps.get_model('portal','PortalSettings')
    Opportunity=apps.get_model('portal','Opportunity')
    CompanyLead=apps.get_model('portal','CompanyLead')
    now=timezone.now()
    # Supersede every automatic Focus rebuild left over from older releases. 0.10.106
    # scheduler uses blank-only backfill and never launches a full taxonomy rebuild.
    stale=BackgroundJob.objects.filter(status__in=['queued','running']).filter(
        label__icontains='Focus taxonomy'
    )
    stale.update(status='stopped',message='Superseded by ScoutBox 0.10.106 blank-only Focus recovery',finished_at=now)
    BackgroundJob.objects.filter(status__in=['queued','running'],label__icontains='Rebuild Focus').update(
        status='stopped',message='Superseded by ScoutBox 0.10.106 blank-only Focus recovery',finished_at=now
    )
    BackgroundJob.objects.filter(status='running',created_at__lt=now-timedelta(hours=6),label__icontains='Focus').update(
        status='stopped',message='Stale Focus job superseded by ScoutBox 0.10.106',finished_at=now
    )
    for ps in PortalSettings.objects.all():
        state=dict(getattr(ps,'focus_taxonomy_state',{}) or {})
        state['automatic_full_rebuild_disabled']=True
        state['v010106_recovery_at']=now.isoformat()
        ps.focus_taxonomy_state=state
        ps.focus_taxonomy_version='0.10.106'
        # Force the one-time repair job to run under 0.10.106 as well.
        ps.integrity_repair_version=''
        ps.save(update_fields=['focus_taxonomy_state','focus_taxonomy_version','integrity_repair_version'])
    # 0.10.107 removed campaign-dominance Focus assignment. Older installations that
    # already ran the previous 0.10.106 migration are repaired by 0127. New upgrades
    # leave blank Focus rows pending for content-only/Local-AI backfill.
    # User requested hidden-lead notes to be cleared in this release; old unsuitable-
    # opportunity notes were too specific and not useful in the list.
    CompanyLead.objects.exclude(note='').update(note='')
    # Remove work-arrangement prose from role_location. Geographic countries already live
    # in country; remote/hybrid details belong in the Remote column.
    for row in Opportunity.objects.exclude(role_location='').iterator(chunk_size=500):
        text=str(getattr(row,'role_location','') or '')
        if len(text)>35 and REMOTE_ROLE_LOCATION_RE.search(text):
            row.role_location=''
            row.save(update_fields=['role_location'])


class Migration(migrations.Migration):
    dependencies=[('portal','0125_v010105_focus_templates_identity')]
    operations=[migrations.RunPython(repair_v010106_state, migrations.RunPython.noop)]
