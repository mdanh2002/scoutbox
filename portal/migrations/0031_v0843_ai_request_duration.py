from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0030_v0838_hidden_lead_company_info')]

    operations = [
        migrations.AddField(
            model_name='airequestlog',
            name='duration_ms',
            field=models.PositiveIntegerField(blank=True, db_index=True, help_text='End-to-end model request duration in milliseconds.', null=True),
        ),
    ]
