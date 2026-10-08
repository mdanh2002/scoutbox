from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.99').exists():
        AuditLog.objects.create(
            actor='system',
            action='version_upgraded',
            version='0.11.99',
            summary='ScoutBox upgraded to version 0.11.99.',
            metadata={
                'version': '0.11.99',
                'release': 'dashboard density, tracking editor, telemetry alignment, audit/history and list-view polish',
            },
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0170_v01198_focus_search_ui')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
