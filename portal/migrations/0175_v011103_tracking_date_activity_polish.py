from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.103').exists():
        AuditLog.objects.create(action='version_upgraded',version='0.11.103',summary='ScoutBox upgraded to version 0.11.103.',metadata={'release':'0.11.103'})

class Migration(migrations.Migration):
    dependencies=[('portal','0174_v011102_tracking_filter_vram_followups')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
