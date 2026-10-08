from pathlib import Path
import ast
import importlib.util
import sys
from types import SimpleNamespace

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

# Release identity.
assert read('VERSION').strip()=='0.11.136'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.136'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.136'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.136'
assert (root/'docs/RELEASE_NOTES_0.11.136.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-28 16:34:00'" in read('opportunity_portal/settings.py')

# SearchAPI missing credentials are configuration state, not provider requests.
search=read('portal/services/search.py')
assert 'ScoutBox/0.11.136' in search
assert "if str(getattr(source,'name','') or '').startswith('SearchAPI ·'):" in search
assert "if not provider_credential_state(source).get('api_configured'):\n                return [],'SearchAPI is not configured.'" in search
assert "if str(getattr(source,'name','') or '').startswith('SearchAPI ·') and not state.get('api_configured'):" in search
assert "'message':'SearchAPI API key is not configured. Save the API key before testing.'" in search
# The automatic search_source preflight must happen before timing/pacing/recording.
fn_start=search.index('def search_source(')
fn_end=search.index('\n\n\ndef test_search_provider',fn_start)
fn=search[fn_start:fn_end]
assert fn.index("SearchAPI is not configured") < fn.index('started=time.time()')
assert fn.index("SearchAPI is not configured") < fn.index('_wait_for_provider_pacing')
assert fn.index("SearchAPI is not configured") < fn.rindex('_record(source,started')
# Manual no-key test preflight must happen before started=time.time and before any _record.
test_start=search.index('def test_search_provider(')
test=search[test_start:]
assert test.index("SearchAPI API key is not configured. Save the API key before testing.") < test.index('started=time.time()')

# Existing routing/logging contract is preserved.
assert "provider='SearchAPI',model=model,stage='searchapi_research',runtime='cloud'" in search
assert "model=('searchapi-'+reported) if not reported.startswith('searchapi-') else reported" in search
assert "elif source.name=='SearchAPI · ChatGPT Research': return [],'SearchAPI ChatGPT Research is an AI research service; use the dedicated research route.'" in search
assert "if automatic and _direct_cloud_ai_available():" in search
assert "provider__in=['openai','gemini','openrouter']" in search
assert "return max(0,min(10000,int(getattr(cfg,'searchapi_daily_limit',500))))" in search

# Migration removes only false no-key telemetry and repairs counters.
migration=read('portal/migrations/0208_v011136_searchapi_ui_cleanup.py')
assert "dependencies=[('portal','0207_v011135_unified_searchapi')]" in migration
assert "'searchapi api key is not configured'" in migration
assert "UsageMetric.objects.filter(provider__in=names,stage='query')" in migration
assert "AIRequestLog.objects.filter(provider='SearchAPI',runtime='cloud',stage='searchapi_research',ok=False)" in migration
assert "stat.requests=max(0,int(stat.requests or 0)-count)" in migration
assert "version='0.11.136'" in migration
mig_tree=ast.parse(migration)
helper=next(n for n in mig_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_is_false_unconfigured_attempt')
assign=next(n for n in mig_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_FALSE_CREDENTIAL_ERRORS' for t in n.targets))
ns={}
exec(compile(ast.fix_missing_locations(ast.Module(body=[assign,helper],type_ignores=[])),'<migration-helper>','exec'),ns)
assert ns['_is_false_unconfigured_attempt']('SearchAPI API key is not configured. Save it first.')
assert not ns['_is_false_unconfigured_attempt']('SearchAPI request failed: HTTP 401 invalid API key')

# Unified SearchAPI popup refinements.
tpl=read('templates/portal/sources.html')
assert '<b>{{s.display_name|default:s.name}}</b>' in tpl
status=tpl[tpl.index('<div class="provider-status-line">'):tpl.index('{% if s.searchapi_hub %}',tpl.index('<div class="provider-status-line">'))]
assert 'SearchAPI API' not in status
assert '{% if not s.searchapi_hub %}' in tpl
assert '<div class="searchapi-save-row"><button class="btn small primary searchapi-save-button">Save</button></div>' in tpl
assert 'searchapi-service-save-row' not in tpl
assert '<h3 class="source-schedule-title">SearchAPI Limit</h3>' not in tpl
assert 'One shared request pool across all SearchAPI services. Manual Test Search requests also count toward this limit.' not in tpl
assert 'name="searchapi_daily_limit"' in tpl and 'min="0" max="10000"' in tpl
# SearchAPI is the last limit row before schedule actions.
limit_pos=tpl.index('name="searchapi_daily_limit"')
actions_pos=tpl.index('<div class="section-actions"><button class="btn primary">Save</button><button class="btn ghost" name="action" value="restore_defaults">',limit_pos)
assert limit_pos < actions_pos
# Test Search row order stays input -> dropdown -> button.
row_start=tpl.index('<div class="searchapi-test-row">')
row_end=tpl.index('</div></div><div id="provider-test-',row_start)
row=tpl[row_start:row_end]
assert row.index('<input') < row.index('<select') < row.index('>Test Search</button>')

# Popup scrolls vertically and does not require horizontal overflow.
css=read('portal/static/portal/app.css')
assert '.searchapi-provider-card{width:min(920px,calc(100vw - 32px))!important;max-width:min(920px,calc(100vw - 32px))!important;max-height:88vh;overflow-y:auto;overflow-x:hidden' in css
assert '.searchapi-save-row{display:flex;justify-content:flex-start' in css
assert '.provider-history-no-x{max-height:330px;overflow-y:auto;overflow-x:hidden' in css
assert '.searchapi-history-table{width:100%!important;min-width:0!important;table-layout:fixed}' in css
# Hover/focus must preserve the exact pressure category color.
for state,color in [('unused','#718b9c'),('healthy','#42d98b'),('warning','#e8b84f'),('critical','#ef6b73')]:
    assert f'.quota-indicator.quota-state-{state}:hover,.quota-indicator.quota-state-{state}:focus-visible{{color:{color}!important}}' in css
    assert f'.quota-indicator.quota-state-{state}:not(.info-only):hover,.quota-indicator.quota-state-{state}:not(.info-only):focus-visible{{color:{color}!important}}' in css

# Gauge threshold semantics remain correct.
views=read('portal/views.py')
view_tree=ast.parse(views)
quota_node=next(n for n in view_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_quota_pressure_state')
quota_ns={}
exec(compile(ast.fix_missing_locations(ast.Module(body=[quota_node],type_ignores=[])),'<quota-state>','exec'),quota_ns)
q=quota_ns['_quota_pressure_state']
assert q(0,100)=='unused'
assert q(1,100)=='healthy' and q(59,100)=='healthy'
assert q(60,100)=='warning' and q(900,1000)=='warning'
assert q(901,1000)=='critical' and q(1000,1000)=='critical'
assert q(5999437,60000000)=='healthy'
assert q(248865,1000000)=='healthy'

# Prior global coverage and re-evaluation safeguards remain.
spec=importlib.util.spec_from_file_location('v011136_discovery_markets',root/'portal/services/discovery_markets.py')
dm=importlib.util.module_from_spec(spec); sys.modules[spec.name]=dm; spec.loader.exec_module(dm)
assert len(dm.DEFAULT_MARKET_CODES)>=190
for code in ('us','gb','au','sg','hk','cn','tw','id','th','vn','ng','ke','ar','cl'):
    assert code in dm.MARKET_BY_CODE, code
of_source=read('portal/services/opportunity_filter.py')
of_tree=ast.parse(of_source)
for node in ast.walk(of_tree):
    assert not (isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.UAdd))
tasks=read('portal/tasks.py')
assert 'MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD = 3' in tasks
assert 'def _bounded_parallel_futures' in tasks

fresh=read('portal/services/fresh_sources.py')
assert 'ScoutBox/0.11.136' in fresh
assert 'ScoutBox/0.11.135' not in fresh

print('ScoutBox 0.11.136 targeted regression checks passed')
