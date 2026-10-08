from pathlib import Path
import ast
from collections import Counter
from urllib.parse import urlparse

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.114'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.114'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.114'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.114'
assert (root / 'docs/RELEASE_NOTES_0.11.114.md').exists()

views = read('portal/views.py')
stats = read('templates/portal/stats.html')

# The old internal-status visualization is gone and the domain chart is wired through.
assert 'Opportunity Status' not in stats
assert 'status-chart' not in stats
assert 'status-summary-data' not in stats
assert '<h3>Opportunity by Domain</h3>' in stats
assert "opportunity-domain-pie" in stats
assert "opportunity-domain-data" in stats
assert 'def _stats_opportunity_domain_rows(qs, limit=8):' in views
assert "opportunity_domains=_stats_opportunity_domain_rows(qs)" in views
assert "opportunity_domain_json=opportunity_domains" in views
assert "qs.values('status').annotate" not in views[views.index('def stats_view(request):'):views.index('def _stats_map_base_querysets', views.index('def stats_view(request):'))]

# The domain helper mirrors Opportunities' displayed URL/domain choice.
assert "raw=str(target_url or url or '').strip()" in views
assert ".lower().split('@')[-1].split(':')[0].removeprefix('www.')" in views
assert "ranked[:limit]" in views and "ranked[limit:]" in views

# Multi-location country values are normalized into separate chart rows.
assert 'def _stats_location_distribution(qs):' in views
assert "normalize_location_items(locations or country" in views
assert 'by_country=_stats_location_distribution(qs)' in views
assert 'lead_by_country=_stats_location_distribution(leads)' in views
assert "values('country').annotate" not in views[views.index('def stats_view(request):'):views.index('def _stats_map_base_querysets', views.index('def stats_view(request):'))]

# All visible pie slices have matching legend entries; the top 8 + Other policy is explicit.
assert 'let rows=raw.slice(0,8);const other=raw.slice(8)' in stats
assert 'rows.forEach((row,i)=>{const y=30+i*27' in stats
assert "x.fillText(String(row.name),lx+14,y)" in stats
assert "drawOpportunityDomain();drawProvider();" in stats

# Exercise the two new helpers without importing Django by compiling their AST nodes.
module = ast.parse(views)
funcs = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in {'_stats_opportunity_domain_rows','_stats_location_distribution'}]
assert len(funcs) == 2
code = compile(ast.Module(body=funcs, type_ignores=[]), 'portal/views.py', 'exec')

def normalize_location_items(value, **kwargs):
    if isinstance(value, list):
        return value
    aliases = {'us':'United States','usa':'United States','france':'France'}
    out=[]
    for token in str(value or '').split(','):
        token=token.strip()
        if not token:
            continue
        label=aliases.get(token.casefold(), token)
        out.append({'label':label})
    return out

env={'Counter':Counter,'urlparse':urlparse,'normalize_location_items':normalize_location_items}
exec(code, env)

class Values:
    def __init__(self, rows): self.rows=rows
    def iterator(self, chunk_size=500): return iter(self.rows)
class QS:
    def __init__(self, rows): self.rows=rows
    def values_list(self, *fields): return Values(self.rows)

normalised_domains = env['_stats_opportunity_domain_rows'](QS([
    (1,'https://www.LinkedIn.com/jobs/1','https://fallback.invalid/1'),
    (2,'','https://jobicy.com/jobs/2'),
    (3,'https://linkedin.com/jobs/3',''),
]), limit=20)
assert normalised_domains == [
    {'name':'linkedin.com','n':2},
    {'name':'jobicy.com','n':1},
]

domain_rows = env['_stats_opportunity_domain_rows'](QS([
    (1,'https://www.LinkedIn.com/jobs/1','https://fallback.invalid/1'),
    (2,'','https://jobicy.com/jobs/2'),
    (3,'https://linkedin.com/jobs/3',''),
    (4,'https://a.example/4',''), (5,'https://b.example/5',''), (6,'https://c.example/6',''),
    (7,'https://d.example/7',''), (8,'https://e.example/8',''), (9,'https://f.example/9',''),
    (10,'https://g.example/10',''), (11,'https://h.example/11',''), (12,'https://i.example/12',''),
]))
assert domain_rows[0] == {'name':'linkedin.com','n':2}
assert domain_rows[-1]['name'] == 'Other' and domain_rows[-1]['n'] == 3
assert sum(row['n'] for row in domain_rows) == 12

country_rows = env['_stats_location_distribution'](QS([
    (1,'United States, France',[]),
    (2,'France',[]),
    (3,'ignored',[{'label':'United States'},{'label':'Canada'}]),
]))
country_counts={row['country']:row['n'] for row in country_rows}
assert country_counts == {'France':2,'United States':2,'Canada':1}
assert 'United States, France' not in country_counts

mig = read('portal/migrations/0186_v011114_statistics_domain_country.py')
assert "version='0.11.114'" in mig
assert '0185_v011113_date_range_validation' in mig
print('ScoutBox 0.11.114 targeted regression checks passed')
