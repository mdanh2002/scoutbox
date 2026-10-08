from django.db import migrations


LEGACY_BROAD_FOCUS_LABELS = (
    'Retro Computing',
    'Retro / Legacy Systems',
    'Retro and Legacy Systems',
)


def forwards(apps, schema_editor):
    Opportunity = apps.get_model('portal', 'Opportunity')
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    Contact = apps.get_model('portal', 'Contact')
    AuditLog = apps.get_model('portal', 'AuditLog')

    # These labels were broad enough to pull unrelated software/company records into a
    # misleading bucket. Clear only the derived Focus value; the normal blank-Focus
    # backfill will regroup each row from its own retained evidence. New classification
    # code maps genuine old-system evidence to the narrower display label Vintage Systems.
    for model in (Opportunity, CompanyLead, Contact):
        for label in LEGACY_BROAD_FOCUS_LABELS:
            model.objects.filter(focus__iexact=label).update(focus='')

    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.98').exists():
        AuditLog.objects.create(
            actor='system',
            action='version_upgraded',
            version='0.11.98',
            summary='ScoutBox upgraded to version 0.11.98.',
            metadata={
                'version': '0.11.98',
                'release': 'dashboard metrics, recycle-bin geometry, search query cleanup and Focus regrouping',
            },
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0169_v01197_tracking_ui_translation_cleanup')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
