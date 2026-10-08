from django.db import migrations, models


def migrate_response_statuses(apps, schema_editor):
    AIRequestLog = apps.get_model('portal', 'AIRequestLog')

    # 0.9.34 called all syntactically incomplete/truncated structured output
    # "Partial response". Historical rows were not run through the new conservative
    # recovery algorithm, so keep them honest and classify them as malformed rather
    # than pretending they were salvaged.
    AIRequestLog.objects.filter(status='partial_response').update(
        status='malformed_response', ok=False
    )

    # Future/hand-repaired rows may already contain explicit recovery metadata.
    AIRequestLog.objects.filter(metadata__response_recovered=True).exclude(
        status__in=['queued', 'running', 'empty_response', 'failed']
    ).update(status='recovered_response', ok=True)


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0076_v0934_ai_response_statuses'),
    ]

    operations = [
        migrations.AddField(
            model_name='airequestlog',
            name='raw_output_text',
            field=models.TextField(
                blank=True,
                help_text='Original provider output before conservative structured-response recovery; retained for diagnostics.',
            ),
        ),
        migrations.AlterField(
            model_name='airequestlog',
            name='status',
            field=models.CharField(
                choices=[
                    ('queued', 'Queued'),
                    ('running', 'Running'),
                    ('completed', 'Completed'),
                    ('empty_response', 'Empty response'),
                    ('recovered_response', 'Recovered response'),
                    ('malformed_response', 'Malformed response'),
                    ('failed', 'Failed'),
                ],
                db_index=True,
                default='completed',
                max_length=20,
            ),
        ),
        migrations.RunPython(migrate_response_statuses, migrations.RunPython.noop),
    ]
