from django.db import migrations


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    # AuditLog has used summary/metadata since the initial schema and gained
    # the version field in 0.11.86.  Keep this historical migration limited to
    # fields that are present in the migration state at 0166.
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.94').exists():
        AuditLog.objects.create(
            actor='system',
            action='version_upgraded',
            version='0.11.94',
            summary='ScoutBox upgraded to version 0.11.94.',
            metadata={
                'version': '0.11.94',
                'release': 'direct resource sampler, host telemetry continuity, Tracking Link and list UI follow-ups',
            },
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0165_v01193_chart_location_ui_repairs')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
