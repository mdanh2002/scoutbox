from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0091_v01040_local_followup')]
    operations = [
        migrations.AddField(model_name='opportunity', name='role_location', field=models.CharField(blank=True, default='', help_text='Specific job/work location text, separate from company/HQ location.', max_length=240)),
        migrations.AddField(model_name='facebookpage', name='validation_state', field=models.CharField(blank=True, default='unknown', help_text='verified, indexed, unavailable, or unknown relevance-validation state.', max_length=24)),
        migrations.AddField(model_name='facebookpage', name='validation_reason', field=models.CharField(blank=True, default='', max_length=500)),
        migrations.AddField(model_name='facebookpage', name='validated_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(model_name='opportunity', name='list_highlight', field=models.CharField(blank=True, default='', help_text='Concise role-specific technical summary for Opportunity list display (maximum 50 words).', max_length=600)),
    ]
