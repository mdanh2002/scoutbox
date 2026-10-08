import re
from django.db import migrations, models


_SYNTHETIC_SUFFIX = re.compile(
    r"(?i)\s+[—–-]\s+(?:developer-relations/domain fit|technical-writing/domain fit|technical-writing fit|"
    r"firmware/security fit|reversing/security fit|security-research fit|virtualization fit|"
    r"reverse-engineering fit|embedded firmware fit|firmware/low-level fit|low-level embedded fit|"
    r"systems/low-level fit|embedded/RTOS fit|legacy/retro fit|specialist fit|adjacent technical fit)$"
)


def _needs_rebuild(value):
    text=' '.join(str(value or '').split()).strip()
    if not text:
        return True
    if _SYNTHETIC_SUFFIX.search(text):
        return True
    return bool(re.search(r'(?i)\s+[—–-]\s+no strong niche-fit signal in captured JD\.?$', text))


def rebuild_summaries(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    from portal.services.highlights import derive_opportunity_highlight
    batch=[]
    for row in Opportunity.objects.all().iterator(chunk_size=250):
        if not _needs_rebuild(row.list_highlight):
            continue
        value=derive_opportunity_highlight(opportunity=row)[:300]
        if value and value != row.list_highlight:
            row.list_highlight=value
            batch.append(row)
        if len(batch)>=250:
            Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=250)
            batch=[]
    if batch:
        Opportunity.objects.bulk_update(batch,['list_highlight'],batch_size=250)


class Migration(migrations.Migration):
    dependencies=[('portal','0058_v08100_chatbot_mail_summary')]
    operations=[
        migrations.AddField(
            model_name='emailprofile',
            name='outgoing_method',
            field=models.CharField(choices=[('smtp','SMTP'),('resend','Resend API')],default='smtp',max_length=20),
        ),
        migrations.AddField(
            model_name='emailprofile',
            name='resend_api_key_enc',
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(rebuild_summaries, migrations.RunPython.noop),
    ]
