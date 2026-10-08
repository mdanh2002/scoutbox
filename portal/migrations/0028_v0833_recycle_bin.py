from django.db import migrations, models


def remove_legacy_deleted_leads(apps, schema_editor):
    # Hidden Leads are no longer kept as permanent deletion records. Older rows that
    # were hidden by v0.8.32 can be removed so future scans may rediscover them.
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    CompanyLead.objects.filter(user_deleted=True).delete()


class Migration(migrations.Migration):
    dependencies = [('portal', '0027_v0832_deleted_tombstones')]
    operations = [
        migrations.AddField(
            model_name='campaign',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, help_text='When this campaign was moved to the Recycle Bin.', null=True),
        ),
        migrations.AddField(
            model_name='application',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, help_text='When this application/outreach was moved to the Recycle Bin.', null=True),
        ),
        migrations.AlterField(
            model_name='opportunity',
            name='user_deleted',
            field=models.BooleanField(db_index=True, default=False, help_text='Whether this opportunity is currently in the Recycle Bin.'),
        ),
        migrations.AlterField(
            model_name='opportunity',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='companylead',
            name='user_deleted',
            field=models.BooleanField(db_index=True, default=False, help_text='Legacy deletion flag retained for database compatibility.'),
        ),
        migrations.RunPython(remove_legacy_deleted_leads, migrations.RunPython.noop),
    ]
