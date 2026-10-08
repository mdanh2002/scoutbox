from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.109').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.109',
            summary='ScoutBox upgraded to version 0.11.109.',
            metadata={'release': '0.11.109'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0180_v011108_tracking_link_ui_alignment')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
