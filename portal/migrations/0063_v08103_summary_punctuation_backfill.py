import re
from django.db import migrations


def rebuild_summaries(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    try:
        from portal.services.highlights import derive_opportunity_highlight, normalize_ai_fit_summary
    except Exception:
        return
    updates=[]
    for row in Opportunity.objects.all().iterator(chunk_size=250):
        old=' '.join(str(row.list_highlight or '').split()).strip()
        needs=(not old) or bool(re.search(r'\s[—–]\s',old)) or bool(re.search(r'(?i)(?:\bgood\s+fit|\btechnical[- ]?writing\s+fit|\btechnical\s+fit|\bfirmware\s+fit|\bfit)\.?$',old))
        value=old
        if needs:
            try: value=derive_opportunity_highlight(opportunity=row)
            except Exception: value=''
            if not value:
                value=re.sub(r'\s+[—–]\s+','; ',old)
                value=re.sub(r'(?i)\s*[-:;,]?\s*(?:good\s+fit|technical[- ]?writing\s+fit|technical\s+fit|firmware\s+fit)\.?$','',value).strip(' ,;:-')
        value=normalize_ai_fit_summary(value,max_words=50)
        if value != old:
            row.list_highlight=value[:300]; updates.append(row)
            if len(updates)>=250:
                Opportunity.objects.bulk_update(updates,['list_highlight'],batch_size=250); updates=[]
    if updates: Opportunity.objects.bulk_update(updates,['list_highlight'],batch_size=250)


class Migration(migrations.Migration):
    dependencies=[('portal','0062_v08103_company_context_backfill')]
    operations=[migrations.RunPython(rebuild_summaries,migrations.RunPython.noop)]
