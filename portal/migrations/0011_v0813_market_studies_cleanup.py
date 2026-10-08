from django.db import migrations
import re
from urllib.parse import urlparse

HOSTS={
    'google.com','bing.com','duckduckgo.com','search.brave.com','yahoo.com','linkedin.com','indeed.com','glassdoor.com',
    'facebook.com','instagram.com','twitter.com','x.com','reddit.com','youtube.com','tiktok.com','monster.com','ziprecruiter.com',
    'simplyhired.com','wellfound.com','seek.com','jobsdb.com','github.com','bitbucket.org','gitlab.com','medium.com','dev.to',
    'substack.com','stackoverflow.com','stackexchange.com','sourceforge.net','npmjs.com','pypi.org','wordpress.com','blogspot.com',
    'hashnode.com','news.ycombinator.com',
}
COMPANIES={re.sub(r'[^a-z0-9]+','',x) for x in (
    'google bing duckduckgo yahoo linkedin indeed glassdoor facebook instagram twitter reddit youtube tiktok monster '
    'ziprecruiter simplyhired wellfound seek jobsdb github bitbucket gitlab medium devto substack stackoverflow stackexchange '
    'sourceforge npmjs pypi wordpress blogspot hashnode ycombinator'
).split()}

def host_is_general(value):
    try:
        host=urlparse(str(value or '')).netloc.lower().split('@')[-1].split(':')[0]
        if host.startswith('www.'): host=host[4:]
    except Exception:
        return False
    return any(host==d or host.endswith('.'+d) for d in HOSTS)

def key(value):
    return re.sub(r'[^a-z0-9]+','',str(value or '').lower())

def forwards(apps,schema_editor):
    Lead=apps.get_model('portal','CompanyLead')
    rows=list(Lead.objects.all().order_by('-score','-created_at','pk'))
    seen=set()
    for row in rows:
        k=key(row.company)
        if k in COMPANIES or host_is_general(row.target_url) or host_is_general(row.source_url) or host_is_general(row.search_url):
            row.delete(); continue
        if k and k in seen:
            row.delete(); continue
        if k: seen.add(k)

class Migration(migrations.Migration):
    dependencies=[('portal','0010_v0812_applied_performance_cleanup')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
