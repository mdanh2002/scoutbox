from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0032_v0844_cloud_limits_openrouter_nvidia'),
    ]

    operations = [
        # The 0.8.44 OpenRouter-only dollar guardrail implied that OpenRouter was the
        # canonical cloud route.  Cloud safety is provider-neutral in 0.8.45 and is
        # enforced through request/search/token limits regardless of vendor.
        migrations.RemoveField(
            model_name='portalsettings',
            name='cloud_openrouter_daily_usd',
        ),
        migrations.RemoveField(
            model_name='cloudbudgetusage',
            name='openrouter_cost_usd',
        ),
    ]
