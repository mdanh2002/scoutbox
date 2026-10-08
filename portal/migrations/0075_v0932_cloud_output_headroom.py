from django.db import migrations


OLD_OUTPUT_DEFAULTS = {
    'url_scrape': 3000,
    'jd_analysis': 650,
    'first_filter': 300,
    'company_enrichment': 500,
    'freshness': 300,
    'page_summarization': 550,
    'cv_tailoring': 1800,
    'email_draft': 900,
    'question_answers': 1600,
    'cold_contact': 650,
    'import_inference': 1800,
}

NEW_OUTPUT_DEFAULTS = {
    'url_scrape': 6000,
    'jd_analysis': 3000,
    'first_filter': 1800,
    'company_enrichment': 2200,
    'freshness': 1600,
    'page_summarization': 2200,
    'cv_tailoring': 3600,
    'email_draft': 2400,
    'question_answers': 3600,
    'cold_contact': 3000,
    'import_inference': 4200,
}


def upgrade_cloud_output_caps(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    for ps in PortalSettings.objects.all().iterator():
        routes = ps.cloud_web_stage_routes if isinstance(ps.cloud_web_stage_routes, dict) else {}
        changed = False
        updated = {}
        for stage, value in routes.items():
            row = dict(value or {})
            old_default = OLD_OUTPUT_DEFAULTS.get(stage)
            new_default = NEW_OUTPUT_DEFAULTS.get(stage)
            if old_default and new_default:
                try:
                    current = int(row.get('max_output_tokens') or old_default)
                except Exception:
                    current = old_default
                # Preserve intentional custom caps. Only upgrade the historical ScoutBox
                # defaults (or a missing value that resolved to that default).
                if current == old_default:
                    row['max_output_tokens'] = new_default
                    changed = True
            updated[stage] = row
        if changed:
            ps.cloud_web_stage_routes = updated
            ps.save(update_fields=['cloud_web_stage_routes'])


def downgrade_cloud_output_caps(apps, schema_editor):
    PortalSettings = apps.get_model('portal', 'PortalSettings')
    for ps in PortalSettings.objects.all().iterator():
        routes = ps.cloud_web_stage_routes if isinstance(ps.cloud_web_stage_routes, dict) else {}
        changed = False
        updated = {}
        for stage, value in routes.items():
            row = dict(value or {})
            old_default = OLD_OUTPUT_DEFAULTS.get(stage)
            new_default = NEW_OUTPUT_DEFAULTS.get(stage)
            if old_default and new_default:
                try:
                    current = int(row.get('max_output_tokens') or new_default)
                except Exception:
                    current = new_default
                if current == new_default:
                    row['max_output_tokens'] = old_default
                    changed = True
            updated[stage] = row
        if changed:
            ps.cloud_web_stage_routes = updated
            ps.save(update_fields=['cloud_web_stage_routes'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0074_v0922_cloud_web_stage_routes')]
    operations = [migrations.RunPython(upgrade_cloud_output_caps, downgrade_cloud_output_caps)]
