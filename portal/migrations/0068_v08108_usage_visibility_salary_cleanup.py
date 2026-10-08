from datetime import datetime, time, timedelta
import re

from django.db import migrations, models
from django.db.models import Sum
from django.utils import timezone


def backfill_usage_fields(apps, schema_editor):
    UsageMetric = apps.get_model('portal', 'UsageMetric')
    CloudBudgetUsage = apps.get_model('portal', 'CloudBudgetUsage')
    Opportunity = apps.get_model('portal', 'Opportunity')

    batch=[]
    for row in UsageMetric.objects.all().iterator(chunk_size=500):
        meta=row.metadata if isinstance(row.metadata, dict) else {}
        try:
            row.reasoning_tokens=max(0,int(meta.get('reasoning_tokens') or meta.get('thoughtsTokenCount') or 0))
        except Exception:
            row.reasoning_tokens=0
        try:
            row.web_search_queries=max(0,int(meta.get('web_queries_count') or meta.get('web_search_queries') or 0))
        except Exception:
            row.web_search_queries=0
        batch.append(row)
        if len(batch)>=500:
            UsageMetric.objects.bulk_update(batch,['reasoning_tokens','web_search_queries'],batch_size=500)
            batch=[]
    if batch:
        UsageMetric.objects.bulk_update(batch,['reasoning_tokens','web_search_queries'],batch_size=500)

    # Rebuild the new informational split counters from historical cloud usage metrics.
    # The pre-existing tokens_out_reasoning field remains the authoritative hard-limit
    # safety counter and is deliberately not rewritten by this migration.
    cloud=('openai','gemini','openrouter')
    tz=timezone.get_current_timezone()
    for budget in CloudBudgetUsage.objects.all().iterator(chunk_size=200):
        start=timezone.make_aware(datetime.combine(budget.day,time.min),tz)
        end=start+timedelta(days=1)
        sums=UsageMetric.objects.filter(provider__in=cloud,at__gte=start,at__lt=end).aggregate(
            output=Sum('tokens_out'), reasoning=Sum('reasoning_tokens'))
        budget.tokens_out=max(0,int(sums.get('output') or 0))
        budget.reasoning_tokens=max(0,int(sums.get('reasoning') or 0))
        budget.save(update_fields=['tokens_out','reasoning_tokens','updated_at'])

    # Clean false salary strings where the only numeric information is a publication
    # year, e.g. "Backend Developer Salary in Germany [2023]".
    currency_or_period=re.compile(r'[$£€¥₹]|\b(?:SGD|USD|AUD|CAD|GBP|EUR|JPY|INR|MYR|HKD|NZD|CHF)\b|\bper\s+(?:year|month|day|hour)\b|/(?:yr|year|mo|month|hr|hour)\b',re.I)
    for row in Opportunity.objects.exclude(salary_text='').iterator(chunk_size=500):
        text=' '.join(str(row.salary_text or '').split())
        if not re.search(r'\b(?:salary|pay|compensation)\b',text,re.I) or currency_or_period.search(text):
            continue
        all_nums=re.findall(r'(?<![A-Za-z0-9])(\d[\d,.]*\s*[kKmM]?)(?![A-Za-z0-9])',text)
        if not all_nums:
            continue
        years=[]; valid=True
        for token in all_nums:
            clean=token.strip().replace(',','')
            if not re.fullmatch(r'\d{4}',clean):
                valid=False; break
            year=int(clean)
            if not 1900 <= year <= 2100:
                valid=False; break
            years.append(year)
        if not valid or not years:
            continue
        row.salary_text=''; row.salary_currency=''; row.salary_min=None; row.salary_max=None
        row.salary_period=''; row.salary_source_type=''; row.salary_source_url=''; row.salary_confidence=0
        row.save(update_fields=['salary_text','salary_currency','salary_min','salary_max','salary_period','salary_source_type','salary_source_url','salary_confidence','updated_at'])


class Migration(migrations.Migration):
    dependencies=[('portal','0067_v08107_resource_usage_stale_contact_cleanup')]
    operations=[
        migrations.AddField(model_name='usagemetric',name='reasoning_tokens',field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='usagemetric',name='web_search_queries',field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='airequestlog',name='reasoning_tokens',field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='airequestlog',name='web_search_queries',field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='airequestlog',name='token_usage_source',field=models.CharField(choices=[('provider_reported','Provider reported'),('estimated','Estimated'),('unknown','Unknown')],default='unknown',max_length=24)),
        migrations.AddField(model_name='cloudbudgetusage',name='tokens_out',field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name='cloudbudgetusage',name='reasoning_tokens',field=models.PositiveBigIntegerField(default=0)),
        migrations.RunPython(backfill_usage_fields,migrations.RunPython.noop),
    ]
