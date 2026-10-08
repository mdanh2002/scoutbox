from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.107').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.107',
            summary='ScoutBox upgraded to version 0.11.107.',
            metadata={'release': '0.11.107'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0178_v011106_tracking_blog_base_generation')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
