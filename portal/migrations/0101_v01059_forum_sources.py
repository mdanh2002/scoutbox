from django.db import migrations, models


def seed_forum_sources(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    try:
        from portal.services.forum_sources import seed_forum_sources as seed
        seed(SearchSource)
    except Exception:
        # Migrations must remain upgrade-safe; the management command can retry seeding.
        pass


def unseed_forum_sources(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    SearchSource.objects.filter(source_type='forum').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0100_v01055_campaign_worker_contact_fit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opportunity',
            name='channel',
            field=models.CharField(
                choices=[
                    ('email', 'Direct email'),
                    ('ats', 'ATS'),
                    ('website', 'Website form'),
                    ('public', 'Public post'),
                    ('community', 'Community'),
                    ('forum', 'Forum'),
                    ('unknown', 'Unknown'),
                ],
                default='unknown',
                max_length=30,
            ),
        ),
        migrations.RunPython(seed_forum_sources, unseed_forum_sources),
    ]
