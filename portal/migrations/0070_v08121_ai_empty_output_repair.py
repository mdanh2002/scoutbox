from django.db import migrations


SYNTHETIC_EMPTY_OUTPUT_ERROR = 'AI provider returned no visible output.'


def repair_synthetic_empty_output_rows(apps, schema_editor):
    AIRequestLog = apps.get_model('portal', 'AIRequestLog')
    ids=[row.pk for row in AIRequestLog.objects.filter(error=SYNTHETIC_EMPTY_OUTPUT_ERROR).only('pk','output_text') if not str(row.output_text or '').strip()]
    if ids:
        AIRequestLog.objects.filter(pk__in=ids).update(
            error='',
            status='completed',
            ok=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0069_v08111_chatbot_source'),
    ]

    operations = [
        migrations.RunPython(repair_synthetic_empty_output_rows, migrations.RunPython.noop),
    ]
