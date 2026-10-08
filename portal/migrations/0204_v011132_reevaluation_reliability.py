from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.132').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.132',
            summary='ScoutBox upgraded to version 0.11.132.',
            metadata={'release': '0.11.132'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0203_v011131_cover_letter_table_alignment')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
