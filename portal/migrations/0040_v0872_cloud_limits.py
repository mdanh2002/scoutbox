from django.db import migrations, models


OLD_TO_NEW = {
    'cloud_min_interval_minutes': (360, 60),
    'cloud_auto_runs_per_campaign_day': (4, 16),
    'cloud_requests_per_run': (20, 100),
    'cloud_web_searches_per_run': (50, 120),
    'cloud_discovery_candidates_per_run': (20, 50),
    'cloud_deep_research_candidates_per_run': (10, 30),
    'cloud_daily_requests': (120, 1200),
    'cloud_daily_web_searches': (200, 2000),
    'cloud_daily_input_tokens': (500000, 5000000),
    'cloud_daily_output_tokens': (75000, 750000),
    'cloud_passive_enrichment_per_day': (10, 100),
    'cloud_page_recovery_per_day': (5, 50),
    'cloud_test_searches_per_run': (10, 20),
    'cloud_test_candidates': (10, 20),
}


def upgrade_untouched_defaults(apps, schema_editor):
    Settings = apps.get_model('portal', 'PortalSettings')
    row = Settings.objects.filter(pk=1).first()
    if not row:
        return
    changed=[]
    for field,(old,new) in OLD_TO_NEW.items():
        if getattr(row,field,None) == old:
            setattr(row,field,new); changed.append(field)
    if changed:
        row.save(update_fields=changed)
    Provider = apps.get_model('portal', 'AIProviderConfig')
    # 2,000 was the previous UI/default cap and caused grounded JSON truncation. Preserve
    # explicit custom values, but upgrade untouched cloud-provider caps to the new default.
    Provider.objects.filter(provider__in=['openai','gemini','openrouter'], max_output_tokens=2000).update(max_output_tokens=8000)


class Migration(migrations.Migration):
    dependencies = [('portal', '0039_v0869_ai_request_status_source_cleanup')]

    operations = [
        migrations.AlterField(model_name='portalsettings', name='cloud_min_interval_minutes', field=models.PositiveIntegerField(default=60)),
        migrations.AlterField(model_name='portalsettings', name='cloud_auto_runs_per_campaign_day', field=models.PositiveIntegerField(default=16)),
        migrations.AlterField(model_name='portalsettings', name='cloud_requests_per_run', field=models.PositiveIntegerField(default=100)),
        migrations.AlterField(model_name='portalsettings', name='cloud_web_searches_per_run', field=models.PositiveIntegerField(default=120)),
        migrations.AlterField(model_name='portalsettings', name='cloud_discovery_candidates_per_run', field=models.PositiveIntegerField(default=50)),
        migrations.AlterField(model_name='portalsettings', name='cloud_deep_research_candidates_per_run', field=models.PositiveIntegerField(default=30)),
        migrations.AlterField(model_name='portalsettings', name='cloud_daily_requests', field=models.PositiveIntegerField(default=1200)),
        migrations.AlterField(model_name='portalsettings', name='cloud_daily_web_searches', field=models.PositiveIntegerField(default=2000)),
        migrations.AlterField(model_name='portalsettings', name='cloud_daily_input_tokens', field=models.PositiveIntegerField(default=5000000)),
        migrations.AlterField(model_name='portalsettings', name='cloud_daily_output_tokens', field=models.PositiveIntegerField(default=750000)),
        migrations.AlterField(model_name='portalsettings', name='cloud_passive_enrichment_per_day', field=models.PositiveIntegerField(default=100)),
        migrations.AlterField(model_name='portalsettings', name='cloud_page_recovery_per_day', field=models.PositiveIntegerField(default=50)),
        migrations.AlterField(model_name='portalsettings', name='cloud_test_searches_per_run', field=models.PositiveIntegerField(default=20)),
        migrations.AlterField(model_name='portalsettings', name='cloud_test_candidates', field=models.PositiveIntegerField(default=20)),
        migrations.RunPython(upgrade_untouched_defaults, migrations.RunPython.noop),
    ]
