from django.db import migrations


def mark_company_domain_refresh(apps, schema_editor):
    """Re-queue completed Company Info rows that still lack a resolved company domain.

    Network work is deliberately left to the bounded maintenance task after startup.
    """
    for model_name in ('Opportunity', 'CompanyLead', 'Contact'):
        Model = apps.get_model('portal', model_name)
        for row in Model.objects.exclude(company_intel={}).iterator():
            company = str(getattr(row, 'company', '') or '').strip()
            if not company:
                continue
            intel = row.company_intel if isinstance(row.company_intel, dict) else {}
            structured = intel.get('structured') if isinstance(intel.get('structured'), dict) else {}
            if structured.get('domain_age_domain') and (
                structured.get('domain_age_label') or structured.get('domain_age_years') not in (None, '')
            ):
                continue
            updated = dict(intel)
            st = dict(structured)
            st['domain_age_refresh_needed'] = True
            st.pop('domain_age_checked_at', None)
            updated['structured'] = st
            row.company_intel = updated
            row.save(update_fields=['company_intel'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0118_v01095_corrective_release')]
    operations = [
        migrations.RunPython(mark_company_domain_refresh, migrations.RunPython.noop),
    ]
