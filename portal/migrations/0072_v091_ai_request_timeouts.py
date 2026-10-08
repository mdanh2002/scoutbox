from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0071_v08124_ai_empty_output_warning'),
    ]

    operations = [
        migrations.AddField(
            model_name='portalsettings',
            name='local_ai_request_timeout_seconds',
            field=models.PositiveSmallIntegerField(default=180, help_text='Per-attempt timeout for local Ollama generation requests.'),
        ),
        migrations.AddField(
            model_name='portalsettings',
            name='cloud_ai_request_timeout_seconds',
            field=models.PositiveSmallIntegerField(default=120, help_text='Per-attempt timeout for Cloud AI generation/web-research requests.'),
        ),
        migrations.AddField(
            model_name='portalsettings',
            name='chatbot_provider_timeout_seconds',
            field=models.PositiveSmallIntegerField(default=300, help_text='Per-provider-attempt timeout for Ask ScoutBox primary and secondary routes.'),
        ),
    ]
