from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.118').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.118',
            summary='ScoutBox upgraded to version 0.11.118.',
            metadata={'release': '0.11.118'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0189_v011117_remove_provider_query_hard_cap')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
