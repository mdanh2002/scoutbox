from django.db import migrations, models


WARNING_CODE = 'empty_output'
WARNING_DETAIL = 'AI request returned no visible output.'
LEGACY_ERROR = 'AI provider returned no visible output.'


def mark_historical_empty_outputs_as_warning(apps, schema_editor):
    AIRequestLog = apps.get_model('portal', 'AIRequestLog')
    batch=[]
    qs=(AIRequestLog.objects.filter(models.Q(status='completed') | models.Q(error=LEGACY_ERROR))
        .exclude(provider='')
        .only('pk','output_text','metadata','status','ok','error'))
    for row in qs.iterator(chunk_size=500):
        if str(row.output_text or '').strip():
            continue
        meta=dict(row.metadata or {})
        meta.setdefault('warning_code', WARNING_CODE)
        meta.setdefault('warning_detail', WARNING_DETAIL)
        row.status='warning'
        row.ok=False
        row.error=''
        row.metadata=meta
        batch.append(row)
        if len(batch)>=500:
            AIRequestLog.objects.bulk_update(batch,['status','ok','error','metadata'],batch_size=500)
            batch=[]
    if batch:
        AIRequestLog.objects.bulk_update(batch,['status','ok','error','metadata'],batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0070_v08121_ai_empty_output_repair'),
    ]

    operations = [
        migrations.AlterField(
            model_name='airequestlog',
            name='status',
            field=models.CharField(
                choices=[
                    ('queued','Queued'),('running','Running'),('completed','Completed'),
                    ('warning','Warning'),('failed','Failed'),
                ],
                db_index=True,
                default='completed',
                max_length=20,
            ),
        ),
        migrations.RunPython(mark_historical_empty_outputs_as_warning, migrations.RunPython.noop),
    ]
