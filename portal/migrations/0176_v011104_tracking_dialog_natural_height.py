from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.104').exists():
        AuditLog.objects.create(action='version_upgraded',version='0.11.104',summary='ScoutBox upgraded to version 0.11.104.',metadata={'release':'0.11.104'})

class Migration(migrations.Migration):
    dependencies=[('portal','0175_v011103_tracking_date_activity_polish')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
