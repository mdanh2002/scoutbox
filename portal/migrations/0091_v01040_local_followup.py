from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0090_v01037_discovery_cleanup')]

    operations = [
        migrations.AddField(
            model_name='portalsettings',
            name='followup_pages_per_run',
            field=models.PositiveIntegerField(default=50, help_text='Maximum extra linked pages Local AI Discovery may inspect per campaign run; 0 disables follow-up exploration.'),
        ),
        migrations.AddField(
            model_name='portalsettings',
            name='followup_link_depth',
            field=models.PositiveSmallIntegerField(default=3, help_text='Maximum Local AI follow-up link depth. Values above 5 are not accepted by the settings UI.'),
        ),
    ]
