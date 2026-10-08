from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('portal', '0012_v0814_dashboard_discovery')]
    operations = [
        migrations.AddField(
            model_name='portalsettings',
            name='error_notifications_seen_at',
            field=models.DateTimeField(default=django.utils.timezone.now, help_text='Dashboard visit watermark used for the new-error badge.'),
        ),
        migrations.AddField(
            model_name='companylead',
            name='summary',
            field=models.TextField(blank=True, default='', help_text='Short company/market-study summary derived from public page evidence.'),
        ),
    ]
