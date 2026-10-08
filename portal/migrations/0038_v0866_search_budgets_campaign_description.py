from django.db import migrations, models

def split_legacy_provider_budget(apps, schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings')
    for row in PortalSettings.objects.all():
        legacy=int(getattr(row,'provider_daily_request_budget',100) or 100)
        if legacy==100:
            row.provider_public_daily_request_budget=5000
            row.provider_api_daily_request_budget=500
        else:
            # Preserve an explicitly customized pre-0.8.66 value for both access modes.
            row.provider_public_daily_request_budget=legacy
            row.provider_api_daily_request_budget=legacy
        row.save(update_fields=['provider_public_daily_request_budget','provider_api_daily_request_budget'])

def reverse_noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies=[('portal','0037_v0863_contact_new_seen')]
    operations=[
        migrations.AddField(model_name='portalsettings',name='provider_public_daily_request_budget',field=models.PositiveIntegerField(default=5000)),
        migrations.AddField(model_name='portalsettings',name='provider_api_daily_request_budget',field=models.PositiveIntegerField(default=500)),
        migrations.AddField(model_name='campaign',name='description',field=models.TextField(blank=True,help_text='Informational campaign description shown only on Campaign Detail.',max_length=2000)),
        migrations.AlterField(model_name='portalsettings',name='keywords_per_run',field=models.PositiveIntegerField(default=100)),
        migrations.AlterField(model_name='portalsettings',name='queries_per_provider',field=models.PositiveIntegerField(default=100)),
        migrations.AlterField(model_name='portalsettings',name='max_results_per_query',field=models.PositiveIntegerField(default=100)),
        migrations.RunPython(split_legacy_provider_budget,reverse_noop),
    ]
