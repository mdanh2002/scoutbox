from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0046_v0880_blacklist_enforcement')]

    operations = [
        migrations.AddField(model_name='campaignrun', name='heartbeat_at', field=models.DateTimeField(blank=True, help_text='Last confirmed campaign activity/progress heartbeat.', null=True)),
        migrations.AddField(model_name='campaignrun', name='stage', field=models.CharField(blank=True, default='', help_text='Current execution stage for progress/stall diagnostics.', max_length=120)),
        migrations.AddField(model_name='campaignrun', name='execution_provider', field=models.CharField(blank=True, default='', max_length=80)),
        migrations.AddField(model_name='campaignrun', name='execution_model', field=models.CharField(blank=True, default='', max_length=200)),
        migrations.AddField(model_name='campaignrun', name='stall_reason', field=models.CharField(blank=True, default='', max_length=500)),
        migrations.AddField(model_name='contact', name='company_intel', field=models.JSONField(blank=True, default=dict, help_text='Compact public company facts associated with this Address Book entry.')),
    ]
