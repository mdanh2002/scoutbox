from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.115').exists():
        AuditLog.objects.create(
            action='version_upgraded',
            version='0.11.115',
            summary='ScoutBox upgraded to version 0.11.115.',
            metadata={'release': '0.11.115'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0186_v011114_statistics_domain_country')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
