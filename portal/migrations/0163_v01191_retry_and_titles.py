from django.db import migrations, models


def forwards(apps, schema_editor):
    FacebookPage=apps.get_model('portal','FacebookPage')
    AuditLog=apps.get_model('portal','AuditLog')

    # 0.11.90 could leave unresolved page titles in a terminal state that required a
    # manual retry. Re-open only blank-title rows so 0.11.91's bounded automatic task
    # can make a fresh set of attempts without touching successfully resolved pages.
    FacebookPage.objects.filter(enabled=True,deleted_at__isnull=True,page_title='').update(
        validation_state='pending',
        validation_reason='Page-title validation queued for automatic retries.',
        title_retry_count=0,
        title_retry_started_at=None,
    )

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.91').exists():
        AuditLog.objects.create(
            actor='system', action='version_upgraded', version='0.11.91',
            summary='ScoutBox upgraded to version 0.11.91.',
            metadata={'version':'0.11.91'},
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0162_v01190_ui_consistency')]
    operations=[
        migrations.AddField(
            model_name='facebookpage',
            name='title_retry_count',
            field=models.PositiveSmallIntegerField(default=0, help_text='Automatic page-title validation attempts made for the current unresolved title.'),
        ),
        migrations.AddField(
            model_name='facebookpage',
            name='title_retry_started_at',
            field=models.DateTimeField(blank=True, help_text='When automatic page-title retries started for the current unresolved title.', null=True),
        ),
        migrations.RunPython(forwards,migrations.RunPython.noop),
    ]
