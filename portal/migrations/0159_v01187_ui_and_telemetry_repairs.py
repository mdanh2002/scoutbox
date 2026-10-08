from django.db import migrations


def forward(apps, schema_editor):
    AuditLog=apps.get_model('portal','AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.87').exists():
        AuditLog.objects.create(
            actor='system',action='version_upgraded',version='0.11.87',
            summary='ScoutBox upgraded to version 0.11.87.',
            metadata={'version':'0.11.87'},
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0158_v01186_audit_facebook_pages')]
    operations=[migrations.RunPython(forward,migrations.RunPython.noop)]
