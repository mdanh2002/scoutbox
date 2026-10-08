from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0122_v010102_focus_ai_rebuild'),
    ]

    operations = [
        migrations.AddField(
            model_name='portalsettings',
            name='country_repair_version',
            field=models.CharField(blank=True, default='', help_text='Last release whose evidence-grounded country/location repair completed.', max_length=32),
        ),
    ]
