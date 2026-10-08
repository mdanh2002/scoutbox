from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0029_v0834_lead_recycle')]
    operations = [
        migrations.AddField(
            model_name='companylead',
            name='company_intel',
            field=models.JSONField(blank=True, default=dict, help_text='Collected public company information for this Hidden Lead.'),
        ),
    ]
