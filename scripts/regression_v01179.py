from pathlib import Path


root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.79'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.79'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.79'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.79'
assert (root/'docs/RELEASE_NOTES_0.11.79.md').exists()

sources=read('templates/portal/sources.html')
settings=read('templates/portal/settings.html')
views=read('portal/views.py')
tasks=read('portal/tasks.py')
markets=read('portal/services/discovery_markets.py')
discovery=read('portal/services/discovery.py')
location=read('portal/services/location.py')
locations=read('portal/services/location_values.py')
pagefetch=read('portal/services/pagefetch.py')
css=read('portal/static/portal/app.css')

assert 'English remains the primary discovery language.' not in sources
checkbox='Search selected markets in local languages where useful'
assert sources.index('Additional languages') < sources.index(checkbox) < sources.index('Save Discovery Markets')
assert 'discovery-market-flag' in sources and '{{m.flag}}' in sources
assert 'def market_workload_schedule(' in markets and "idx%4==3" in markets
assert "for source in ('market','additional')" in markets

assert ".exclude(category='discovery_market')" in views
assert 'nonempty_query|nonempty_url|url_list' in views
assert "selected_outcome_label=_filter_options_label('outcomes'" in views
assert "selected_outcome_label=_filter_options_label('outcomes',[{'value':'results'" in views
assert "outcome_state['mode'])," in views
assert "runtime_filter_label=_filter_options_label('runtimes',runtime_options,runtime_values,runtime_state['mode'])" in views
assert "action_filter_label=_filter_options_label('actions',action_options,action_values,action_state['mode'])" in views

assert "if gap_seconds and gap_seconds>=900" in tasks
assert "summary='Background scheduler resumed after 5 minute gap.'" in views
assert 'diagnostic_export_job' in tasks and 'Diagnostic export ready to download' in tasks
assert 'method="post" action="{% url \'export_diagnostic_data\' %}"' in settings
assert 'startDiagnosticExportPolling' in settings and 'diagnostic-export-frame' not in settings
assert 'diagnostic_export_download' in views

assert 'segment_match=re.search' in location and "return legacy_location_text(items)[:240]" in location
assert "result['jobposting_company']" in pagefetch
assert 'and not structured_company' in discovery
assert "_reject('blacklisted_company' if company else 'blacklisted_url')" in discovery
assert 'def _gcc_is_geographic(' in locations and 'gnu compiler' in locations
assert 'overflow:hidden!important' in css and '.search-log-provider-region{' in css

print('ScoutBox 0.11.79 regression checks passed')
