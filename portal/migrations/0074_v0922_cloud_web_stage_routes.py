from django.db import migrations, models


def seed_cloud_stage_routes(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    ps = PortalSettings.objects.filter(pk=1).first()
    if not ps or ps.cloud_web_stage_routes:
        return
    provider = str(ps.cloud_web_provider or '').strip().lower()
    primary = str(ps.cloud_web_primary_model or '').strip()
    secondary = str(ps.cloud_web_secondary_model or '').strip()
    if not provider or not primary:
        return
    stages = [
        'url_scrape','jd_analysis','first_filter','company_enrichment','freshness',
        'page_summarization','cv_tailoring','email_draft','question_answers',
        'cold_contact','import_inference',
    ]
    defaults = {
        'url_scrape': (7000,3000), 'jd_analysis': (4500,650), 'first_filter': (2200,300),
        'company_enrichment': (3000,500), 'freshness': (1800,300), 'page_summarization': (3200,550),
        'cv_tailoring': (10000,1800), 'email_draft': (6500,900), 'question_answers': (9000,1600),
        'cold_contact': (3500,650), 'import_inference': (8000,1800),
    }
    routes = {}
    for stage in stages:
        max_in, max_out = defaults[stage]
        row = {'provider': provider, 'model': primary, 'max_input_tokens': max_in, 'max_output_tokens': max_out}
        if secondary and secondary != primary:
            row.update({'fallback_provider': provider, 'fallback_model': secondary})
        routes[stage] = row
    ps.cloud_web_stage_routes = routes
    ps.save(update_fields=['cloud_web_stage_routes'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0073_v092_campaign_linkage_repair')]
    operations = [
        migrations.AddField(
            model_name='portalsettings',
            name='cloud_web_stage_routes',
            field=models.JSONField(blank=True, default=dict, help_text='Per-stage Cloud Web provider, primary/failover models and token caps. Primary and failover must use the same provider within a stage.'),
        ),
        migrations.RunPython(seed_cloud_stage_routes, migrations.RunPython.noop),
    ]
