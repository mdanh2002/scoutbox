import re

from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def _region(label, code, icon, evidence):
    return {
        'kind':'region','label':label,'code':code,'icon':icon,
        'source':'jobicy_snapshot','evidence':evidence,
    }


def forward(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    Opportunity=apps.get_model('portal','Opportunity')
    Contact=apps.get_model('portal','Contact')
    SourceBlacklist=apps.get_model('portal','SourceBlacklist')

    AuditLog.objects.filter(
        action='scheduler_silence',
        summary='Background scheduler resumed after 5 minute gap.',
    ).delete()

    # Repair the reported Jobicy record from current-listing evidence. The current role
    # explicitly says EMEA or APAC; a related-job employer must not replace Canonical.
    jobicy_role=Opportunity.objects.filter(
        Q(url__icontains='jobicy.com/jobs/151197')|
        Q(search_url__icontains='jobicy.com/jobs/151197')|
        Q(target_url__icontains='jobicy.com/jobs/151197')
    )
    for row in jobicy_role:
        row.company='Canonical'
        row.role_location='APAC, EMEA'
        row.country='APAC, EMEA'
        row.locations=[
            _region('APAC','APAC','apac','Remote from APAC, EMEA'),
            _region('EMEA','EMEA','emea','Remote from APAC, EMEA'),
        ]
        fields=['company','role_location','country','locations','updated_at']
        blocked=SourceBlacklist.objects.filter(
            Q(label__iexact='Canonical')|Q(label__iexact='Canonical Ltd')|Q(label__iexact='Canonical Limited'),
            enabled=True,deleted_at__isnull=True,scope__in=['all','opportunities'],
        ).exists()
        if blocked:
            row.user_deleted=True
            row.deleted_at=timezone.now()
            row.rejection_reason='Blocked by blacklist: Canonical'
            fields.extend(['user_deleted','deleted_at','rejection_reason'])
        row.save(update_fields=fields)

    # Remove compiler-context GCC values that were mistaken for the Gulf region.
    technical=re.compile(r'(?i)\b(?:gnu compiler|compiler|toolchain|cross[- ]compil|buildroot|gcc version|g\+\+)\b')
    for row in Contact.objects.filter(company_country__iexact='GCC'):
        blob=' '.join(str(x or '') for x in (row.company,row.title,row.company_summary,row.source_url,row.company_intel))
        if not technical.search(blob):
            continue
        row.company_country=''
        row.company_locations=[]
        intel=dict(row.company_intel or {})
        intel['facts']=[fact for fact in (intel.get('facts') or []) if not (
            isinstance(fact,dict) and str(fact.get('label') or '').casefold() in {'location','hq','headquarters'} and str(fact.get('value') or '').strip().casefold()=='gcc'
        )]
        row.company_intel=intel
        row.save(update_fields=['company_country','company_locations','company_intel'])


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0155_v01176_worldwide_job_sources')]
    operations=[migrations.RunPython(forward,backward)]
