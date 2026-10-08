from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.101').exists():
        AuditLog.objects.create(action='version_upgraded',version='0.11.101',summary='ScoutBox upgraded to version 0.11.101.',metadata={'release':'0.11.101'})

class Migration(migrations.Migration):
    dependencies=[('portal','0172_v011100_dashboard_hotfix')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
