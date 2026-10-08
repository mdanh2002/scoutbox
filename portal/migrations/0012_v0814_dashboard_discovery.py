from django.db import migrations, models
from urllib.parse import urlparse



def seed_preferred_sources(apps, schema_editor):
    SearchSource = apps.get_model('portal', 'SearchSource')
    SearchSource.objects.filter(name__iexact='Google').update(preferred_initial=True)
    SearchSource.objects.filter(name__iexact='Bing').update(preferred_initial=True)


def repair_market_company_names(apps, schema_editor):
    CompanyLead = apps.get_model('portal', 'CompanyLead')
    two_level = {'co.uk','org.uk','ac.uk','com.au','net.au','org.au','co.nz','com.sg','com.my','co.jp','co.kr','com.br','com.cn','com.tw'}
    for lead in CompanyLead.objects.all().iterator():
        url = lead.target_url or lead.source_url or lead.search_url or ''
        try:
            host = urlparse(url).netloc.lower().split('@')[-1].split(':')[0].removeprefix('www.')
        except Exception:
            continue
        labels = [x for x in host.split('.') if x]
        if len(labels) < 3:
            continue
        tail = '.'.join(labels[-2:])
        domain = '.'.join(labels[-3:]) if tail in two_level and len(labels) >= 3 else tail
        current = ''.join(ch for ch in (lead.company or '').lower() if ch.isalnum())
        first = ''.join(ch for ch in labels[0].lower() if ch.isalnum())
        if current and current == first and domain and domain.lower() != host:
            lead.company = domain[:220]
            lead.save(update_fields=['company'])


class Migration(migrations.Migration):
    dependencies = [('portal', '0011_v0813_market_studies_cleanup')]
    operations = [
        migrations.AddField(model_name='searchsource', name='preferred_initial', field=models.BooleanField(default=False, help_text='Use this search engine for initial URL discovery in Source-Guided Discovery.')),
        migrations.CreateModel(name='CustomSearchDomain', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=160)),
            ('domain', models.CharField(max_length=255, unique=True)),
            ('note', models.TextField(blank=True)),
            ('enabled', models.BooleanField(default=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'ordering': ['name', 'domain']}),
        migrations.AddField(model_name='opportunity', name='note', field=models.TextField(blank=True, default='', help_text='Private note about this opportunity.')),
        migrations.AddField(model_name='companylead', name='note', field=models.TextField(blank=True, default='', help_text='Private note about this Market Studies lead.')),
        migrations.AddField(model_name='resourcesample', name='memory_total_mb', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='resourcesample', name='disk_used_mb', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='resourcesample', name='disk_total_mb', field=models.PositiveIntegerField(default=0)),
        migrations.RunPython(seed_preferred_sources, migrations.RunPython.noop),
        migrations.RunPython(repair_market_company_names, migrations.RunPython.noop),
    ]
