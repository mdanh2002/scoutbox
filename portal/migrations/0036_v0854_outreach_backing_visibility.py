from django.db import migrations


def hide_hidden_lead_outreach_backing_rows(apps, schema_editor):
    Opportunity = apps.get_model('portal', 'Opportunity')
    # Cold outreach drafts historically used an Opportunity row as their backing record
    # because Application has a required one-to-one relationship. Keep that internal
    # compatibility record, but never expose it as a discovered Opportunity.
    Opportunity.objects.filter(
        extracted_facts__outreach=True,
        extracted_facts__market_study_lead_id__isnull=False,
    ).update(suppressed=True)


class Migration(migrations.Migration):
    dependencies = [('portal', '0035_v0853_hidden_lead_noise_defaults')]
    operations = [migrations.RunPython(hide_hidden_lead_outreach_backing_rows, migrations.RunPython.noop)]
