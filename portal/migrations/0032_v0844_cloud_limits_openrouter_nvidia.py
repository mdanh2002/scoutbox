from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('portal', '0031_v0843_ai_request_duration')]

    operations = [
        migrations.AddField(model_name='portalsettings', name='cloud_min_interval_minutes', field=models.PositiveIntegerField(default=360)),
        migrations.AddField(model_name='portalsettings', name='cloud_auto_runs_per_campaign_day', field=models.PositiveIntegerField(default=4)),
        migrations.AddField(model_name='portalsettings', name='cloud_requests_per_run', field=models.PositiveIntegerField(default=20)),
        migrations.AddField(model_name='portalsettings', name='cloud_web_searches_per_run', field=models.PositiveIntegerField(default=50)),
        migrations.AddField(model_name='portalsettings', name='cloud_discovery_candidates_per_run', field=models.PositiveIntegerField(default=20)),
        migrations.AddField(model_name='portalsettings', name='cloud_deep_research_candidates_per_run', field=models.PositiveIntegerField(default=10)),
        migrations.AddField(model_name='portalsettings', name='cloud_daily_requests', field=models.PositiveIntegerField(default=120)),
        migrations.AddField(model_name='portalsettings', name='cloud_daily_web_searches', field=models.PositiveIntegerField(default=200)),
        migrations.AddField(model_name='portalsettings', name='cloud_daily_input_tokens', field=models.PositiveIntegerField(default=500000)),
        migrations.AddField(model_name='portalsettings', name='cloud_daily_output_tokens', field=models.PositiveIntegerField(default=75000)),
        migrations.AddField(model_name='portalsettings', name='cloud_passive_enrichment_per_day', field=models.PositiveIntegerField(default=10)),
        migrations.AddField(model_name='portalsettings', name='cloud_page_recovery_per_day', field=models.PositiveIntegerField(default=5)),
        migrations.AddField(model_name='portalsettings', name='cloud_test_searches_per_run', field=models.PositiveIntegerField(default=10)),
        migrations.AddField(model_name='portalsettings', name='cloud_test_candidates', field=models.PositiveIntegerField(default=10)),
        migrations.AddField(model_name='portalsettings', name='cloud_openrouter_daily_usd', field=models.DecimalField(decimal_places=2, default=5.0, max_digits=8)),
        migrations.AlterField(model_name='aiproviderconfig', name='provider', field=models.CharField(choices=[('ollama','Ollama local'),('openai','OpenAI'),('gemini','Gemini'),('openrouter','OpenRouter')], max_length=30, unique=True)),
        migrations.AddField(model_name='resourcesample', name='gpu_vram_used_mb', field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='resourcesample', name='gpu_vram_total_mb', field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='opportunity', name='ai_state', field=models.JSONField(blank=True, default=dict, help_text='Automatic/manual AI enrichment lifecycle state keyed by enrichment kind and evidence generation.')),
        migrations.AddField(model_name='companylead', name='ai_state', field=models.JSONField(blank=True, default=dict, help_text='Automatic/manual AI enrichment lifecycle state keyed by enrichment kind and evidence generation.')),
        migrations.CreateModel(
            name='CloudBudgetUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField(default=django.utils.timezone.localdate, unique=True)),
                ('requests', models.PositiveIntegerField(default=0)),
                ('web_searches', models.PositiveIntegerField(default=0)),
                ('tokens_in', models.PositiveBigIntegerField(default=0)),
                ('tokens_out_reasoning', models.PositiveBigIntegerField(default=0)),
                ('passive_enrichment', models.PositiveIntegerField(default=0)),
                ('page_recovery', models.PositiveIntegerField(default=0)),
                ('openrouter_cost_usd', models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='CloudRunUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requests', models.PositiveIntegerField(default=0)),
                ('web_searches', models.PositiveIntegerField(default=0)),
                ('discovery_candidates', models.PositiveIntegerField(default=0)),
                ('deep_research_candidates', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign_run', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='cloud_usage', to='portal.campaignrun')),
            ],
        ),
        migrations.CreateModel(
            name='CompanyResearchCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255, unique=True)),
                ('company', models.CharField(blank=True, max_length=220)),
                ('data', models.JSONField(blank=True, default=dict)),
                ('provider', models.CharField(blank=True, max_length=80)),
                ('model', models.CharField(blank=True, max_length=200)),
                ('researched_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('evidence_hash', models.CharField(blank=True, max_length=64)),
            ],
        ),
    ]
