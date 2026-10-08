from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0077_v0935_ai_response_recovery'),
    ]

    operations = [
        migrations.AlterField(
            model_name='backgroundjob',
            name='kind',
            field=models.CharField(
                choices=[
                    ('campaign', 'Campaign discovery'), ('import_text', 'Application import'),
                    ('import_document', 'Document import'), ('mail_scan', 'Mailbox scan'),
                    ('diagnostic', 'Test discovery'), ('hidden_scan', 'Hidden Leads scan'),
                    ('cold_draft', 'Cold outreach draft'), ('enrich', 'Opportunity enrichment'),
                    ('prepare', 'Application preparation'), ('translate', 'Translation'),
                    ('company_research', 'Company research'), ('summarize', 'AI text summary'),
                    ('performance', 'Performance test'), ('chatbot', 'Chatbot request'),
                    ('filter_opportunities', 'Opportunity filter'), ('other', 'Automatic task'),
                ],
                default='other', max_length=30,
            ),
        ),
    ]
