from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.102').exists():
        AuditLog.objects.create(action='version_upgraded',version='0.11.102',summary='ScoutBox upgraded to version 0.11.102.',metadata={'release':'0.11.102'})

class Migration(migrations.Migration):
    dependencies=[('portal','0173_v011101_ui_chatbot_filters')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
