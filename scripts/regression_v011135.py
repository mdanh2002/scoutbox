from pathlib import Path
import ast
import importlib.util
import sys
from types import SimpleNamespace

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

# Release identity.
assert read('VERSION').strip()=='0.11.135'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.135'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.135'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.135'
assert (root/'docs/RELEASE_NOTES_0.11.135.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-28 15:56:00'" in read('opportunity_portal/settings.py')

# New shared SearchAPI limit is schema-backed and migrates safely after 0.11.134.
models=read('portal/models.py')
assert "'searchapi_daily_limit': 500" in models
assert "searchapi_daily_limit = models.PositiveIntegerField" in models
migration=read('portal/migrations/0207_v011135_unified_searchapi.py')
assert "dependencies=[('portal','0206_v011134_community_searchapi_signals')]" in migration
assert "name='searchapi_daily_limit'" in migration and 'default=500' in migration
assert "'SearchAPI · ChatGPT Research':" in migration
assert "SearchAPI · Google AI Mode" in migration and "SearchAPI · Google Local" in migration
assert "version='0.11.135'" in migration

search=read('portal/services/search.py')
for code,name in {
    'jobs':'SearchAPI · Google Jobs','web':'SearchAPI · Google Web','forums':'SearchAPI · Google Forums',
    'news':'SearchAPI · Google News','chatgpt':'SearchAPI · ChatGPT Research',
    'ai_mode':'SearchAPI · Google AI Mode','local':'SearchAPI · Google Local',
}.items():
    assert repr(code) in search and name in search
assert "SEARCHAPI_DEFAULT_AUTO={'jobs':True,'web':True,'forums':True,'news':True,'chatgpt':False,'ai_mode':False,'local':False}" in search
assert "return max(0,min(10000,int(getattr(cfg,'searchapi_daily_limit',500))))" in search
assert "raise RuntimeError('SearchAPI requires an explicit Discovery Market" in search
assert "SEARCHAPI_LOCATIONS_ENDPOINT='https://www.searchapi.io/api/v1/locations'" in search
assert "def _searchapi_canonical_location(source, market):" in search
assert "_searchapi_locale(market,source)" in search

# ChatGPT is a separate Cloud Runtime log path and never an ordinary search_source route.
assert "def search_searchapi_chatgpt_research" in search
assert "provider='SearchAPI',model=model,stage='searchapi_research',runtime='cloud'" in search
assert "model=('searchapi-'+reported) if not reported.startswith('searchapi-') else reported" in search
assert "_record_searchapi_chatgpt" in search
assert "elif source.name=='SearchAPI · ChatGPT Research': return [],'SearchAPI ChatGPT Research is an AI research service; use the dedicated research route.'" in search
assert "if automatic and _direct_cloud_ai_available():" in search
assert "return {'ok':False,'skipped':'direct_cloud_preferred'" in search
assert "provider__in=['openai','gemini','openrouter']" in search
assert "'web_search':'true'" in search
assert "(data.get('response_metadata') or {}).get('model')" in search

# SearchAPI AI answer parser supports current text_blocks[].answer payload shape.
search_tree=ast.parse(search)
answer_node=next(n for n in search_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_searchapi_ai_answer')
answer_ns={}
exec(compile(ast.fix_missing_locations(ast.Module(body=[answer_node],type_ignores=[])),'<searchapi-answer>','exec'),answer_ns)
text=answer_ns['_searchapi_ai_answer']({'text_blocks':[{'type':'paragraph','answer':'One.'},{'type':'unordered_list','items':[{'answer':'Two.'},'Three.']}]})
assert 'One.' in text and 'Two.' in text and 'Three.' in text
model_node=next(n for n in search_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_searchapi_reported_model')
model_ns={}
exec(compile(ast.fix_missing_locations(ast.Module(body=[model_node],type_ignores=[])),'<searchapi-model>','exec'),model_ns)
assert model_ns['_searchapi_reported_model']({'response_metadata':{'model':'gpt-5-test'}},'chatgpt')=='gpt-5-test'

# AI Mode and Local are real SearchAPI adapters and remain non-ChatGPT Search Activity lanes.
assert "def search_searchapi_google_ai_mode" in search and "'google_ai_mode'" in search
assert "def search_searchapi_google_local" in search and "'google_local'" in search
assert "'_signal_only':True" in search and "'_community_kind':'employer_discovery'" in search
assert "_record(source,started,len(rows),'',bytes_downloaded=size,usage_category='searchapi_ai_research'" in search
assert "metadata__searchapi_service='chatgpt'" in search

# Automatic AI research has independent sparse caps subordinate to the shared quota.
assert "default_limit=10 if service in {'chatgpt','ai_mode'} else 0" in search
assert "if provider_budget_remaining(source)<=0:" in search
assert "return bool(limit and _searchapi_ai_auto_count(service)<limit)" in search

# Non-ChatGPT SearchAPI attempts are UsageMetric stage=query, ChatGPT is AIRequestLog only.
views=read('portal/views.py')
assert "Non-ChatGPT SearchAPI work comes from Search Activity (UsageMetric stage=query)." in views
assert "ChatGPT comes from AIRequestLog/Cloud Runtime and is not duplicated into Search Activity." in views
assert "UsageMetric.objects.filter(provider__in=names,stage='query')" in views
assert "AIRequestLog.objects.filter(provider='SearchAPI',runtime='cloud',stage='searchapi_research')" in views
assert "'searchapi_daily_limit':(0,10000,SEARCH_SCHEDULE_DEFAULTS['searchapi_daily_limit'])" in views
assert "source.display_name='SearchAPI'" in views
assert "if source.name.startswith('SearchAPI ·') and source.pk!=getattr(searchapi_hub,'pk',None):\n            continue" in views

# Gauge threshold semantics execute independently of Django.
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
assert q(10,0)=='unused'

# Unified SearchAPI UI: only hub is rendered, usage toggles, and test controls are in the requested order.
tpl=read('templates/portal/sources.html')
assert 'SearchAPI API key' in tpl and 'ScoutBox usage' in tpl
for code in ('jobs','web','forums','news','chatgpt','ai_mode','local'):
    assert f"value=\"{{{{service.code}}}}\"" in tpl or 'name="searchapi_services"' in tpl
assert '>Test Search<' in tpl
row_start=tpl.index('<div class="searchapi-test-row">')
row_end=tpl.index('</div></div><div id="provider-test-',row_start)
row=tpl[row_start:row_end]
assert row.index('<input') < row.index('<select') < row.index('>Test Search</button>')
assert 'id="provider-service-{{s.pk}}"' in row
assert "chatgpt:'Find current evidence that Acme Robotics is hiring embedded engineers'" in tpl
assert '<th>Service</th><th>Query</th>' in tpl
assert 'name="searchapi_daily_limit"' in tpl and 'min="0" max="10000"' in tpl
assert 'quota-state-{{searchapi_quota_summary.state' in tpl

css=read('portal/static/portal/app.css')
assert '.searchapi-test-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(180px,240px) auto' in css
assert '.provider-history-no-x{max-height:330px;overflow-y:auto;overflow-x:hidden' in css
assert '.searchapi-history-table{width:100%!important;min-width:0!important;table-layout:fixed}' in css
assert '.quota-indicator.quota-state-unused:not(.info-only){color:#718b9c!important}' in css
assert '.quota-indicator.quota-state-healthy:not(.info-only){color:#42d98b!important}' in css
assert '.quota-indicator.quota-state-warning:not(.info-only){color:#e8b84f!important}' in css
assert '.quota-indicator.quota-state-critical:not(.info-only){color:#ef6b73!important}' in css

# Test job preserves service choice so disabled services remain manually testable.
tasks=read('portal/tasks.py')
assert "def search_provider_test_job(self, job_id, source_id, force_public=False, query='ScoutBox test', service=''):" in tasks
assert "source=searchapi_source(service) or source" in tasks
assert "result=test_search_provider(source,query=query or 'ScoutBox test',force_public=bool(force_public),limit=5)" in tasks
assert "search_provider_test_job.delay(job.pk,source.pk,bool(request.POST.get('force_public')),query,service)" in views

# Community/blocked-listing integration is preserved and SearchAPI research is last-resort only.
discovery=read('portal/services/discovery.py')
assert "SearchAPI · Google Local" in discovery
assert "SearchAPI Google Local employer discovery → localized careers/hiring verification" in discovery
assert "site:{host} (careers OR jobs OR hiring)" in discovery
assert "def _searchapi_corroborate_community_signal" in discovery
assert "purpose='community_signal_corroboration'" in discovery
assert "AI text alone is never" in discovery
assert "'_supplemental_signal_source'=kind" not in discovery  # guard typo: metadata assignment uses dict syntax below
assert "item['_supplemental_signal_source']=kind" in discovery
assert "searchapi_research(research_query,market=market,purpose='blocked_listing_rescue',automatic=True,limit=6)" in discovery
assert "Any replacement URL must independently pass" in discovery
assert "_capture_community_hiring_signal(" in discovery
assert "signal_only=bool(result.get('_signal_only') or result.get('_news_signal'))" in discovery

# 0.11.133 worldwide/global coverage remains.
spec=importlib.util.spec_from_file_location('v011135_discovery_markets',root/'portal/services/discovery_markets.py')
dm=importlib.util.module_from_spec(spec); sys.modules[spec.name]=dm; spec.loader.exec_module(dm)
assert len(dm.DEFAULT_MARKET_CODES)>=190
for code in ('us','gb','au','sg','hk','cn','tw','id','th','vn','ng','ke','ar','cl'):
    assert code in dm.MARKET_BY_CODE, code
cfg=SimpleNamespace(discovery_markets=['us','gb','au','sg','hk','id','vn'],discovery_market_strategy='global')
evidence={'us':{'attempts':100},'gb':{'attempts':40},'au':{'attempts':30},'sg':{'attempts':20},'hk':{'attempts':10},'id':{'attempts':0},'vn':{'attempts':0}}
plan=dm.market_plan(cfg,campaign_id=2,rotation_offset=0,evidence=evidence)
assert plan['effective_strategy']=='global'
assert plan['ordered_codes'].index('id') < plan['ordered_codes'].index('us')
assert plan['ordered_codes'].index('vn') < plan['ordered_codes'].index('us')

# 0.11.132 re-evaluation safety stays intact.
of_source=read('portal/services/opportunity_filter.py')
of_tree=ast.parse(of_source)
for node in ast.walk(of_tree):
    assert not (isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.UAdd)), 'unexpected unary + in opportunity_filter.py'
assert 'MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD = 3' in tasks
assert 'def _bounded_parallel_futures' in tasks

# Versioned network user agent updated.
fresh=read('portal/services/fresh_sources.py')
assert 'ScoutBox/0.11.135' in fresh
assert 'ScoutBox/0.11.134' not in fresh

print('ScoutBox 0.11.135 targeted regression checks passed')
