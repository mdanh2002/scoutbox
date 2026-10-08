from django.db import migrations, models
import re
from urllib.parse import urlsplit


def suppress_known_aggregate_listings(apps, schema_editor):
    Opportunity=apps.get_model('portal','Opportunity')
    def collection(url):
        try:
            p=urlsplit(str(url or '')); host=(p.hostname or '').lower().removeprefix('www.'); path=(p.path or '').lower()
        except Exception:
            return False
        if (host.endswith('indeed.com') or host.startswith('indeed.') or '.indeed.' in host) and re.match(r'^/q-.+-jobs\.html/?$',path): return True
        if (host.endswith('indeed.com') or host.startswith('indeed.') or '.indeed.' in host) and path.rstrip('/') in ('/jobs','/jobs/search','/jobs/browse'): return True
        if host.endswith('linkedin.com') and any(path.startswith(x) for x in ('/jobs/search','/jobs/collections','/jobs/search-results')): return True
        if (host.endswith('glassdoor.com') or host.startswith('glassdoor.') or '.glassdoor.' in host) and any(x in path for x in ('/job/jobs.htm','/job/index.htm','/job/search')): return True
        return False

    ids=[]
    for row in Opportunity.objects.filter(suppressed=False,user_deleted=False).only('id','url','search_url','target_url'):
        if any(collection(url) for url in (row.url,row.search_url,row.target_url)):
            ids.append(row.id)
    if ids:
        Opportunity.objects.filter(id__in=ids).update(
            suppressed=True,
            rejection_reason='Multi-job listing/aggregator page; individual roles must be expanded before persistence.',
        )


class Migration(migrations.Migration):
    dependencies = [('portal', '0028_v0833_recycle_bin')]
    operations = [
        migrations.AlterField(
            model_name='companylead',
            name='user_deleted',
            field=models.BooleanField(db_index=True, default=False, help_text='Whether this Hidden Lead is currently in the Recycle Bin.'),
        ),
        migrations.AlterField(
            model_name='companylead',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, help_text='When this Hidden Lead was moved to the Recycle Bin.', null=True),
        ),
        migrations.RunPython(suppress_known_aggregate_listings, migrations.RunPython.noop),
    ]
