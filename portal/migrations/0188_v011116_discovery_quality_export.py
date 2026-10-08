from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.116').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.116',
            summary='ScoutBox upgraded to version 0.11.116.',
            metadata={'release': '0.11.116'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0187_v011115_concise_search_queries')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
