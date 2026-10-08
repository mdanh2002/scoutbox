import re
from django.db import migrations, models


AREA_PREFIX = re.compile(
    r'^\s*(?:relevant\s+(?:technical\s+)?(?:work|areas?|experience|skills?|signals?)|technical\s+areas?|areas?)\s*:\s*',
    re.I,
)


def forwards(apps, schema_editor):
    Opportunity = apps.get_model('portal', 'Opportunity')
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    Application = apps.get_model('portal', 'Application')
    # Existing records pre-date read tracking. Mark them read so only records arriving
    # after the upgrade appear as New.
    Opportunity.objects.all().update(is_read=True)
    CompanyLead.objects.all().update(is_read=True)
    for app in Application.objects.exclude(created_at=None).iterator():
        Opportunity.objects.filter(pk=app.opportunity_id, application_draft_requested_at=None).update(application_draft_requested_at=app.created_at)
    for lead in CompanyLead.objects.exclude(match_summary='').iterator():
        text=(lead.match_summary or '').strip()
        cleaned=text
        # Some old releases produced nested labels such as
        # "Relevant work: Relevant technical work: QEMU". Strip all leading labels.
        while True:
            newer=AREA_PREFIX.sub('', cleaned, count=1).strip()
            if newer == cleaned:
                break
            cleaned=newer
        if cleaned != text:
            lead.match_summary=cleaned
            lead.save(update_fields=['match_summary'])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0007_v085_market_studies_sources')]
    operations=[
        migrations.AddField(
            model_name='opportunity',
            name='is_read',
            field=models.BooleanField(default=False, help_text='Whether the opportunity has been opened/reviewed in ScoutBox.'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='application_draft_requested_at',
            field=models.DateTimeField(blank=True, help_text='When Create Application Draft / Prepare Application was first requested.', null=True),
        ),
        migrations.AddField(
            model_name='companylead',
            name='is_read',
            field=models.BooleanField(default=False, help_text='Whether the Market Studies lead details have been reviewed.'),
        ),
        migrations.AlterField(
            model_name='backgroundjob',
            name='kind',
            field=models.CharField(
                choices=[
                    ('campaign','Campaign discovery'),('import_text','Application import'),('import_document','Document import'),
                    ('mail_scan','Mailbox scan'),('diagnostic','Test discovery'),('hidden_scan','Market Studies scan'),
                    ('cold_draft','Cold outreach draft'),('enrich','Opportunity enrichment'),('prepare','Application preparation'),
                    ('translate','Translation'),('company_research','Company research'),('summarize','AI text summary'),
                    ('performance','Performance test'),('other','Automatic task')
                ],
                default='other', max_length=30,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
