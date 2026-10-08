from django.db import migrations, models


def enable_multilingual_exploration(apps, schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings')
    PortalSettings.objects.update(multilingual_exploration_enabled=True)


class Migration(migrations.Migration):
    dependencies=[('portal','0156_v01179_activity_location_repairs')]

    operations=[
        migrations.AlterField(
            model_name='portalsettings',
            name='multilingual_exploration_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(enable_multilingual_exploration,migrations.RunPython.noop),
    ]
