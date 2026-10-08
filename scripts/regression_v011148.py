from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.148'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.148'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.148'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.148'
assert 'The release following 0.11.148 is 0.11.149' in read('RELEASE_POLICY.md')
assert "PORTAL_LAST_MODIFIED = '2026-10-01 12:10:00'" in read('opportunity_portal/settings.py')

markets=read('portal/services/discovery_markets.py')
assert "'English':'en'" in markets and 'def query_language_metadata' in markets
search=read('portal/services/search.py')
assert "query_language='English'" in search
assert "metadata.update(query_language_metadata(query_language))" in search
assert "'provider_locale':" in search
assert 'ScoutBox/0.11.148' in search
discovery=read('portal/services/discovery.py')
assert "planned_query_language=str(query_item.get('multilingual_language') or 'English')" in discovery
assert 'query_language=planned_query_language' in discovery
cold=read('portal/services/cold.py')
assert "query_language=(query_item.get('multilingual_language') or 'English')" in cold
views=read('portal/views.py')
for marker in ('market_mode','query_language_mode','_market_filtered','_query_language_filtered','All Query Languages','All Markets'):
    assert marker in views
assert "metadata__region_setting__iexact=value" not in views[views.index('def search_log_view'):views.index('def gpt_log_view')]
assert "Q(metadata__multilingual_language__iexact=label)" in views
assert "Query Language','Provider Locale'" in views
html=read('templates/portal/search_log.html')
assert 'name="market"' in html and 'name="query_language"' in html
assert 'Search query languages…' in html and 'Search markets…' in html
assert 'name="region"' not in html
settings=read('templates/portal/settings.html')
assert settings.index('diagnostic-export-period-row') < settings.index('diagnostic-export-selections')
assert 'Total (uncompressed)' in settings
assert 'Estimated total before compression:' not in settings
assert "node.textContent=diagnosticFormatBytes(value)" in settings
css=read('portal/static/portal/app.css')
assert '.diagnostic-export-period-row' in css
assert 'border-top:0!important' in css
assert '.search-log-toolbar details.search-language-filter' in css
migration=read('portal/migrations/0220_v011148_search_activity_language_semantics.py')
assert "dependencies=[('portal','0219_v011147_discovery_quality_and_diagnostics')]" in migration
assert "version='0.11.148'" in migration
print('ScoutBox 0.11.148 targeted regression checks passed')
