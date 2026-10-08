from django.db import migrations, models

OPPORTUNITY_DEFAULT = (
    'Verify the role and its work-location rules with web search. Keep it if the candidate can realistically take it from Singapore, work remotely, or relocate with explicit support. Recycle clearly incompatible location-restricted roles unless the opportunity is exceptionally unusual and strongly matched. Convert to Hidden Lead if it is not a real vacancy but shows a strong current need for outside technical help.'
)
HIDDEN_LEAD_DEFAULT = (
    'Verify this company with web search. Keep it only if there is a credible current signal that it may need outside technical help, a developer, contractor, partner, or outsourced expertise. Technical relevance alone is not enough. Convert to Opportunity if it is clearly a live vacancy. If no need signal exists, recycle unless the company is exceptionally unusual and specifically relevant to the candidate; this exception should be very rare.'
)


def forwards(apps, schema_editor):
    AuditLog = apps.get_model('portal', 'AuditLog')
    if not AuditLog.objects.filter(action='version_upgraded', version='0.11.122').exists():
        AuditLog.objects.create(
            action='version_upgraded', version='0.11.122',
            summary='ScoutBox upgraded to version 0.11.122.',
            metadata={'release':'0.11.122'},
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0193_v011121_cross_list_reevaluation')]
    operations = [
        migrations.AddField(
            model_name='portalsettings', name='opportunity_cloud_reevaluation_prompt',
            field=models.TextField(blank=True, default=OPPORTUNITY_DEFAULT),
        ),
        migrations.AddField(
            model_name='portalsettings', name='hidden_lead_cloud_reevaluation_prompt',
            field=models.TextField(blank=True, default=HIDDEN_LEAD_DEFAULT),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
