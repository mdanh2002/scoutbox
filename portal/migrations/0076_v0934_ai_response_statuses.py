from django.db import migrations, models


def split_ai_response_statuses(apps, schema_editor):
    AIRequestLog = apps.get_model('portal', 'AIRequestLog')

    # 0.9.32 used Warning for both empty output and provider truncation. Preserve the
    # distinction when upgrading so historical AI Requests immediately use the new UI.
    AIRequestLog.objects.filter(
        status='warning', metadata__warning_code='response_truncated'
    ).update(status='partial_response', ok=False)
    AIRequestLog.objects.filter(
        status='warning', metadata__response_truncated=True
    ).update(status='partial_response', ok=False)
    AIRequestLog.objects.filter(status='warning').update(status='empty_response', ok=False)

    # A provider-truncated request could have been written as Completed by older builds.
    AIRequestLog.objects.filter(
        status='completed', metadata__response_truncated=True
    ).update(status='partial_response', ok=False)

    # Repair the legacy blank-completed representation too. Placeholder rows are queued
    # or running and are therefore not affected by this completed-only cleanup.
    AIRequestLog.objects.filter(
        status='completed', output_text=''
    ).exclude(provider='').update(status='empty_response', ok=False)


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0075_v0932_cloud_output_headroom'),
    ]

    operations = [
        migrations.AlterField(
            model_name='airequestlog',
            name='status',
            field=models.CharField(
                choices=[
                    ('queued', 'Queued'),
                    ('running', 'Running'),
                    ('completed', 'Completed'),
                    ('empty_response', 'Empty response'),
                    ('partial_response', 'Partial response'),
                    ('failed', 'Failed'),
                ],
                db_index=True,
                default='completed',
                max_length=20,
            ),
        ),
        migrations.RunPython(split_ai_response_statuses, migrations.RunPython.noop),
    ]
