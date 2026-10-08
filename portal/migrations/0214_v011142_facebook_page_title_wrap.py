from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.142').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.142',summary='ScoutBox upgraded to version 0.11.142.',
            metadata={'release':'0.11.142','facebook_page_title_two_line_wrap':True},
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0213_v011141_source_coverage_integrity')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
