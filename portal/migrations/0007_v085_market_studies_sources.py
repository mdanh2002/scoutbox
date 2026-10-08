from django.db import migrations, models


NEW_MARKETPLACES = [
    ('Fiverr', 'https://www.fiverr.com'),
    ('PeoplePerHour', 'https://www.peopleperhour.com'),
    ('Guru', 'https://www.guru.com'),
    ('Truelancer', 'https://www.truelancer.com'),
    ('Workana', 'https://www.workana.com'),
]


def forwards(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    for name, base_url in NEW_MARKETPLACES:
        SearchSource.objects.update_or_create(
            name=name,
            defaults={
                'source_type': 'marketplace',
                'base_url': base_url,
                'category': 'Excluded / low-value marketplaces',
                'enabled': False,
                'low_value_marketplace': True,
            },
        )
    prefix='Relevant technical work: '
    for lead in CompanyLead.objects.filter(match_summary__startswith=prefix).iterator():
        lead.match_summary=(lead.match_summary or '')[len(prefix):].strip()
        lead.save(update_fields=['match_summary'])


def backwards(apps, schema_editor):
    # Data cleanup/seed expansion is intentionally retained on downgrade.
    pass


class Migration(migrations.Migration):
    dependencies=[('portal','0006_v084_cleanup_existing_noise')]
    operations=[
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name='backgroundjob',
            name='kind',
            field=models.CharField(
                choices=[
                    ('campaign','Campaign discovery'),('import_text','Application import'),('import_document','Document import'),
                    ('mail_scan','Mailbox scan'),('diagnostic','Test discovery'),('hidden_scan','Market Studies scan'),
                    ('cold_draft','Cold outreach draft'),('enrich','Opportunity enrichment'),('prepare','Application preparation'),
                    ('translate','Translation'),('company_research','Company research'),('performance','Performance test'),
                    ('other','Automatic task')
                ],
                default='other', max_length=30,
            ),
        ),
    ]
