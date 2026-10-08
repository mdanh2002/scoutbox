from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.149').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.149',summary='ScoutBox upgraded to version 0.11.149.',
            metadata={
                'release':'0.11.149',
                'diagnostic_export_layout_polish':True,
                'presentation_only':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0220_v011148_search_activity_language_semantics')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
