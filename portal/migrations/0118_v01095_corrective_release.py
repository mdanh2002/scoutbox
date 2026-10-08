from django.db import migrations


def normalize_legacy_resend_status(apps, schema_editor):
    """Map legacy successful Resend submissions to Accepted, never Delivered."""
    MailEvent=apps.get_model('portal','MailEvent')
    qs=MailEvent.objects.filter(kind='notification',delivery_status='sent')
    for row in qs.iterator():
        meta=row.metadata if isinstance(row.metadata,dict) else {}
        provider=str(meta.get('provider') or '').casefold()
        server=str(row.server or '').casefold()
        # Old Resend success rows may predate metadata.provider but retain the server
        # label. Either is sufficient evidence that `sent` meant API acceptance.
        if provider=='resend' or 'resend' in server:
            row.delivery_status='accepted'
            row.save(update_fields=['delivery_status'])


def mark_missing_domain_refresh(apps, schema_editor):
    """Re-mark pre-0.10.95 rows that have stored domain evidence but no RDAP age.

    0.10.94's initial migration marked then-existing rows, but company research performed
    later in that release could fail RDAP without retaining the refresh marker. This pass
    is deliberately local-only; the bounded Celery maintenance task performs network work.
    """
    for model_name in ('Opportunity','CompanyLead','Contact'):
        Model=apps.get_model('portal',model_name)
        for row in Model.objects.exclude(company_intel={}).iterator():
            intel=row.company_intel if isinstance(row.company_intel,dict) else {}
            structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
            if structured.get('domain_registered_at') or structured.get('domain_age_years') not in (None,''):
                continue
            sources=intel.get('sources') if isinstance(intel.get('sources'),list) else []
            has_hint=bool(
                structured.get('domain_age_domain') or structured.get('website') or
                structured.get('company_website') or structured.get('company_domain') or
                structured.get('domain') or intel.get('website') or intel.get('company_website')
            )
            if not has_hint:
                has_hint=any(
                    (isinstance(item,dict) and str(item.get('url') or '').startswith(('http://','https://'))) or
                    (isinstance(item,str) and item.startswith(('http://','https://')))
                    for item in sources
                )
            if not has_hint:
                continue
            updated=dict(intel); st=dict(structured)
            st['domain_age_refresh_needed']=True
            # Do not carry a failed-at timestamp from old logic: this upgrade should make
            # one prompt deterministic retry possible after services restart.
            st.pop('domain_age_checked_at',None)
            updated['structured']=st; row.company_intel=updated
            row.save(update_fields=['company_intel'])


class Migration(migrations.Migration):
    dependencies=[('portal','0117_v01094_scheduler_retention_provenance')]
    operations=[
        migrations.RunPython(normalize_legacy_resend_status,migrations.RunPython.noop),
        migrations.RunPython(mark_missing_domain_refresh,migrations.RunPython.noop),
    ]
