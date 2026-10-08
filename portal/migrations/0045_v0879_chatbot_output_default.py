from django.db import migrations


def upgrade_legacy_chatbot_output_default(apps, schema_editor):
    """Move the old shipped 450-token Chatbot answer cap to the current 5k default.

    ScoutBox briefly shipped a 450-token Chatbot default before the model-driven
    workspace assistant. Preserve every other explicit user value.
    """
    AIProviderConfig = apps.get_model('portal', 'AIProviderConfig')
    for cfg in AIProviderConfig.objects.all().iterator(chunk_size=100):
        routes = dict(cfg.stage_routes or {})
        chat = dict(routes.get('chatbot') or {})
        try:
            current = int(chat.get('max_output_tokens') or 0)
        except Exception:
            current = 0
        if current != 450:
            continue
        chat['max_output_tokens'] = 5000
        routes['chatbot'] = chat
        cfg.stage_routes = routes
        cfg.save(update_fields=['stage_routes'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0044_v0878_chatbot_default')]
    operations = [migrations.RunPython(upgrade_legacy_chatbot_output_default, migrations.RunPython.noop)]
