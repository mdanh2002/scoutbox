from django.db import migrations


def remove_addressbook_promotion_history(apps, schema_editor):
    """Remove legacy high-volume promotion diagnostics from Audit Trail.

    0.10.77 keeps future addressbook_promotion rows only for created or materially
    updated contacts. Existing rows predate that invariant, so the requested cleanup
    removes the whole historical action family during upgrade.
    """
    AuditLog = apps.get_model('portal', 'AuditLog')
    AuditLog.objects.filter(action='addressbook_promotion').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0106_v01075_local_ai_lane_defer'),
    ]

    operations = [
        migrations.RunPython(remove_addressbook_promotion_history, migrations.RunPython.noop),
    ]
