from django.db import migrations, models


def seed_cloud_priority(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    row = PortalSettings.objects.filter(pk=1).first()
    if row is not None and not row.cloud_provider_priority:
        row.cloud_provider_priority = ['openai', 'gemini', 'openrouter']
        row.save(update_fields=['cloud_provider_priority'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0033_v0845_provider_neutral_readiness_usage')]

    operations = [
        migrations.AddField(
            model_name='portalsettings',
            name='cloud_provider_priority',
            field=models.JSONField(blank=True, default=list, help_text='Ordered Cloud AI provider preference used only when a stage is Automatic and cloud execution is required.'),
        ),
        migrations.AddField(
            model_name='aiproviderconfig',
            name='capabilities',
            field=models.JSONField(blank=True, default=dict, help_text='Last validated provider/model capability hints, including web research support.'),
        ),
        migrations.AddField(
            model_name='contact',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, help_text='When this Address Book entry was moved to the Recycle Bin.', null=True),
        ),
        migrations.AddField(
            model_name='sourceblacklist',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, help_text='When this blacklist entry was moved to the Recycle Bin.', null=True),
        ),
        migrations.RunPython(seed_cloud_priority, migrations.RunPython.noop),
    ]
