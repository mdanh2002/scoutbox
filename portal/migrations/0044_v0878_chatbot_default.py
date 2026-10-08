from django.db import migrations


def upgrade_chatbot_default(apps, schema_editor):
    """Move only the previous shipped 10k Chatbot answer cap to the new 5k default.

    Explicit user choices other than the exact previous default are preserved.
    Chatbot routing can live on the Ollama holder or an older provider holder, so
    inspect every provider row defensively.
    """
    AIProviderConfig = apps.get_model('portal', 'AIProviderConfig')
    for cfg in AIProviderConfig.objects.all().iterator(chunk_size=100):
        routes = dict(cfg.stage_routes or {})
        chat = dict(routes.get('chatbot') or {})
        try:
            current = int(chat.get('max_output_tokens') or 0)
        except Exception:
            current = 0
        if current != 10000:
            continue
        chat['max_output_tokens'] = 5000
        routes['chatbot'] = chat
        cfg.stage_routes = routes
        cfg.save(update_fields=['stage_routes'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0043_v0877_limits_contacts_postage')]
    operations = [migrations.RunPython(upgrade_chatbot_default, migrations.RunPython.noop)]
