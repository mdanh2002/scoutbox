from django.db import migrations, models


def backfill_locations(apps, schema_editor):
    try:
        from portal.services.location_values import parse_location_items, normalize_location_items, legacy_location_text
    except Exception:
        return
    Opportunity = apps.get_model('portal', 'Opportunity')
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    Contact = apps.get_model('portal', 'Contact')

    for row in Opportunity.objects.order_by('pk').iterator(chunk_size=200):
        parts = []
        for value, source in ((getattr(row, 'role_location', ''), 'role_location'), (getattr(row, 'country', ''), 'country'), (getattr(row, 'remote_text', ''), 'remote_text')):
            parts.extend(parse_location_items(value, source=source, evidence=str(value or '')))
        facts = getattr(row, 'extracted_facts', None) or {}
        if isinstance(facts, dict):
            for key in ('direct_role_location_hint', 'jobGeo', 'job_location', 'location'):
                if facts.get(key):
                    parts.extend(parse_location_items(facts.get(key), source='extracted_facts.' + key, evidence=str(facts.get(key) or '')))
            acq = facts.get('acquisition') if isinstance(facts.get('acquisition'), dict) else {}
            for key in ('jobGeo', 'location', 'role_location'):
                if acq.get(key):
                    parts.extend(parse_location_items(acq.get(key), source='acquisition.' + key, evidence=str(acq.get(key) or '')))
        items = normalize_location_items(parts)
        if items:
            row.locations = items
            legacy = legacy_location_text(items)
            if legacy and legacy != getattr(row, 'country', ''):
                row.country = legacy
            row.save(update_fields=['locations', 'country'])

    for row in CompanyLead.objects.order_by('pk').iterator(chunk_size=200):
        parts = parse_location_items(getattr(row, 'country', ''), source='country', evidence=getattr(row, 'country', '') or '')
        intel = getattr(row, 'company_intel', None) or {}
        if isinstance(intel, dict):
            structured = intel.get('structured') if isinstance(intel.get('structured'), dict) else {}
            for key in ('headquarters', 'hq', 'company_location', 'location', 'base_location'):
                if structured.get(key):
                    parts.extend(parse_location_items(structured.get(key), source='company_intel.structured.' + key, evidence=str(structured.get(key) or '')))
        items = normalize_location_items(parts)
        if items:
            row.locations = items
            legacy = legacy_location_text(items)
            if legacy and legacy != getattr(row, 'country', ''):
                row.country = legacy
            row.save(update_fields=['locations', 'country'])

    for row in Contact.objects.order_by('pk').iterator(chunk_size=200):
        parts = parse_location_items(getattr(row, 'company_country', ''), source='company_country', evidence=getattr(row, 'company_country', '') or '')
        intel = getattr(row, 'company_intel', None) or {}
        if isinstance(intel, dict):
            structured = intel.get('structured') if isinstance(intel.get('structured'), dict) else {}
            for key in ('headquarters', 'hq', 'company_location', 'location', 'base_location'):
                if structured.get(key):
                    parts.extend(parse_location_items(structured.get(key), source='company_intel.structured.' + key, evidence=str(structured.get(key) or '')))
        items = normalize_location_items(parts)
        if items:
            row.company_locations = items
            legacy = legacy_location_text(items)
            if legacy and legacy != getattr(row, 'company_country', ''):
                row.company_country = legacy
            row.save(update_fields=['company_locations', 'company_country'])


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0130_v010110_focus_residual_footer'),
    ]

    operations = [
        migrations.AddField(
            model_name='opportunity',
            name='locations',
            field=models.JSONField(blank=True, default=list, help_text='Evidence-grounded role eligibility locations; supports multiple countries and recruiter regions.'),
        ),
        migrations.AddField(
            model_name='companylead',
            name='locations',
            field=models.JSONField(blank=True, default=list, help_text='Evidence-grounded company/lead locations; supports multiple countries and recruiter regions.'),
        ),
        migrations.AddField(
            model_name='contact',
            name='company_locations',
            field=models.JSONField(blank=True, default=list, help_text='Evidence-grounded Address Book company/team locations; supports multiple countries and recruiter regions.'),
        ),
        migrations.RunPython(backfill_locations, migrations.RunPython.noop),
    ]
