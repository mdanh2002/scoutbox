from urllib.parse import urlparse
from django.db import migrations, models
import django.utils.timezone

GENERAL_HOSTS = {
    'google.com','bing.com','duckduckgo.com','search.brave.com','yahoo.com',
    'linkedin.com','indeed.com','glassdoor.com','facebook.com','instagram.com',
    'twitter.com','x.com','reddit.com','youtube.com','tiktok.com','monster.com',
    'ziprecruiter.com','simplyhired.com','wellfound.com','seek.com','jobsdb.com',
}
GENERAL_COMPANIES = {
    'google','bing','duckduckgo','yahoo','linkedin','indeed','glassdoor','facebook',
    'instagram','twitter','x','reddit','youtube','tiktok','monster','ziprecruiter',
    'simplyhired','wellfound','seek','jobsdb',
}


def _norm_company(value):
    return ''.join(ch for ch in str(value or '').lower() if ch.isalnum())


def _general_url(value):
    try:
        host=(urlparse(str(value or '')).netloc or '').lower().split('@')[-1].split(':')[0]
        if host.startswith('www.'):
            host=host[4:]
    except Exception:
        return False
    return any(host == d or host.endswith('.' + d) for d in GENERAL_HOSTS)


def clean_general_market_rows(apps, schema_editor):
    Lead=apps.get_model('portal','CompanyLead')
    general_names={_norm_company(x) for x in GENERAL_COMPANIES}
    delete_ids=[]
    for lead in Lead.objects.all().only('pk','company','search_url','target_url','source_url').iterator():
        if _norm_company(lead.company) in general_names or any(_general_url(v) for v in (lead.search_url,lead.target_url,lead.source_url)):
            delete_ids.append(lead.pk)
            if len(delete_ids)>=500:
                Lead.objects.filter(pk__in=delete_ids).delete(); delete_ids=[]
    if delete_ids:
        Lead.objects.filter(pk__in=delete_ids).delete()


class Migration(migrations.Migration):
    dependencies=[('portal','0009_v0810_tracking_suffix_reserve')]
    operations=[
        migrations.AddField(
            model_name='application',
            name='date_added',
            field=models.DateTimeField(default=django.utils.timezone.now, help_text='When this applied-role entry was added to ScoutBox.'),
        ),
        migrations.AddField(
            model_name='performancerun',
            name='output_file',
            field=models.FileField(blank=True, upload_to='performance/%Y/%m/'),
        ),
        migrations.RunPython(clean_general_market_rows, migrations.RunPython.noop),
    ]
