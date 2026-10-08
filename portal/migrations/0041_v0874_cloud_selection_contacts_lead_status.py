from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0040_v0872_cloud_limits')]

    operations = [
        migrations.AddField(model_name='portalsettings', name='cloud_web_provider', field=models.CharField(blank=True, default='', help_text='Explicit Cloud Web provider used for discovery/research.', max_length=30)),
        migrations.AddField(model_name='portalsettings', name='cloud_web_primary_model', field=models.CharField(blank=True, default='', help_text='Primary model for Cloud Web discovery/research.', max_length=200)),
        migrations.AddField(model_name='portalsettings', name='cloud_web_secondary_model', field=models.CharField(blank=True, default='', help_text='Secondary model for Cloud Web fallback; must differ from primary.', max_length=200)),
        migrations.AddField(model_name='contact', name='company_summary', field=models.TextField(blank=True, default='', help_text='Short researched summary of what the contact company/team does.')),
        migrations.AddField(model_name='contact', name='company_country', field=models.CharField(blank=True, default='', help_text='Researched company/team location for Address Book context.', max_length=120)),
        migrations.AddField(model_name='companylead', name='target_http_status', field=models.PositiveSmallIntegerField(blank=True, help_text='Most recent direct HTTP status observed for the target URL.', null=True)),
        migrations.AddField(model_name='companylead', name='target_checked_at', field=models.DateTimeField(blank=True, help_text='When the Hidden Lead target URL was last checked directly.', null=True)),
        migrations.AddField(model_name='companylead', name='target_check_error', field=models.CharField(blank=True, default='', help_text='Most recent target URL check error, if any.', max_length=500)),
    ]
