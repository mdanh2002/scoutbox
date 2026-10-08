from pathlib import Path


root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.80'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.80'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.80'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.80'
assert (root/'docs/RELEASE_NOTES_0.11.80.md').exists()
assert (root/'portal/migrations/0157_v01180_multilingual_always_enabled.py').exists()

telemetry=read('templates/portal/telemetry.html')
search_log=read('templates/portal/search_log.html')
sources=read('templates/portal/sources.html')
views=read('portal/views.py')
markets=read('portal/services/discovery_markets.py')
models=read('portal/models.py')
css=read('portal/static/portal/app.css')

assert telemetry.index('Discovery Performance') < telemetry.index('Market Coverage') < telemetry.index('Request Breakdown')
for marker in ('market-coverage-chart','market-language-legend','market-country-legend','market-coverage-data','drawMarketCoverage','market_coverage_legend'):
    assert marker in telemetry
assert 'Outer: search languages · inner: Discovery Markets.' in telemetry
assert 'def _market_coverage_breakdown(' in views
assert 'def _market_coverage_from_rows(' in views
assert "filter(category='discovery_market',stage='query')" in views
assert "metadata__multilingual_language" in views and "language_raw=" in views
assert "'market_coverage':market_coverage" in views
assert "export=='market_coverage_legend'" in views

assert "_date_filter_fields.html" not in search_log
assert search_log.index('provider-filter') < search_log.index('search-region-filter') < search_log.index('outcome-filter')
assert 'name="region"' in search_log and 'Search regions…' in search_log
search_view=views[views.index('def search_log_view('):views.index('\ndef gpt_log_view(',views.index('def search_log_view('))]
assert '_log_date_bounds' not in search_view and '_apply_log_date_bounds' not in search_view
for marker in ('region_mode','regions_selected','metadata__region_setting__iexact','selected_region_label','region_options'):
    assert marker in search_view

assert 'Search selected markets in local languages where useful' not in sources
assert 'name="multilingual_exploration_enabled"' not in sources
assert "ps.multilingual_exploration_enabled=True" in views
assert "if not getattr(settings_obj,'multilingual_exploration_enabled'" not in markets
assert 'multilingual_exploration_enabled = models.BooleanField(default=True)' in models
assert '.market-coverage-card' in css and '.search-region-filter' in css

print('ScoutBox 0.11.80 regression checks passed')
