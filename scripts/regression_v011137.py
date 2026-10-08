from pathlib import Path
import ast
import importlib.util
import sys

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

# Release identity.
assert read('VERSION').strip()=='0.11.137'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.137'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.137'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.137'
assert (root/'docs/RELEASE_NOTES_0.11.137.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-28 17:51:00'" in read('opportunity_portal/settings.py')

search=read('portal/services/search.py')
assert 'ScoutBox/0.11.137' in search
assert 'def validate_searchapi_credential(source, api_key=None, timeout=12):' in search
assert "'q':'ScoutBox API key validation'" in search
assert "'location':'United States'" in search and "'gl':'us'" in search and "'hl':'en'" in search
validator=search[search.index('def validate_searchapi_credential('):search.index('\n\ndef _searchapi_request',search.index('def validate_searchapi_credential('))]
assert '_record(' not in validator and 'UsageMetric' not in validator and 'AIRequestLog' not in validator
assert "return {'status':'valid','ok':True" in validator
assert "return {'status':'invalid','ok':False" in validator
assert "return {'status':'unavailable','ok':False" in validator

# Exercise the validation classifier without importing Django.
tree=ast.parse(search)
nodes=[]
for name in ('_searchapi_error_message','validate_searchapi_credential'):
    nodes.append(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name))
class Resp:
    def __init__(self,status=200,data=None,text=''):
        self.status_code=status; self._data=data or {}; self.text=text
        self.content=b'{}'; self.ok=200<=status<300
    def json(self): return self._data
class RequestsStub:
    RequestException=Exception
    def __init__(self,response=None,exc=None): self.response=response; self.exc=exc
    def get(self,*a,**kw):
        if self.exc: raise self.exc
        return self.response
ns={'SEARCHAPI_ENDPOINT':'https://example.invalid','UA':'ScoutBox test','provider_capability':lambda s:{},'_provider_secret':lambda s,c:'saved-key'}
ns['requests']=RequestsStub(Resp(200,{'search_metadata':{'status':'Success'}}))
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<validator>','exec'),ns)
assert ns['validate_searchapi_credential'](object())['status']=='valid'
ns['requests']=RequestsStub(Resp(401,{'error':{'message':'Invalid API key'}}))
assert ns['validate_searchapi_credential'](object())['status']=='invalid'
ns['requests']=RequestsStub(exc=Exception('offline'))
assert ns['validate_searchapi_credential'](object())['status']=='unavailable'

# AI research defaults increased without removing the shared SearchAPI cap.
assert "default_limit=100 if service in {'chatgpt','ai_mode'} else 0" in search
assert "min(1000,int(cfg.get('auto_daily_limit',default_limit)))" in search
assert "return max(0,min(10000,int(getattr(cfg,'searchapi_daily_limit',500))))" in search
assert "if automatic and _direct_cloud_ai_available():" in search
assert "provider__in=['openai','gemini','openrouter']" in search
assert "provider='SearchAPI',model=model,stage='searchapi_research',runtime='cloud'" in search

views=read('portal/views.py')
assert 'validate_searchapi_credential' in views
assert "cfg['auto_daily_limit']=max(0,min(1000,int(request.POST.get('chatgpt_auto_daily_limit') or 100)))" in views
assert "cfg['auto_daily_limit']=max(0,min(1000,int(request.POST.get('ai_mode_auto_daily_limit') or 100)))" in views
assert "validation=validate_searchapi_credential(source)" in views
assert "hub_cfg['searchapi_validation_status']=validation_state" in views
assert "messages.warning(request,'SearchAPI API key was saved, but validation failed." in views
assert "status_label='Saved, validation failed'" in views
assert "status_label='Saved, validation unavailable'" in views
assert "status_label='Configured'" in views
assert "try: cap=int(cfg.get('auto_daily_limit',100 if code in {'chatgpt','ai_mode'} else 0) or 0)" in views

# Unified SearchAPI dialog presentation.
tpl=read('templates/portal/sources.html')
assert 'searchapi-api-key-wrap' in tpl and 'searchapi-key-status' in tpl
assert '<span class="tag {{s.provider_ui.searchapi_validation_class}}">{{s.provider_ui.searchapi_validation_label}}</span>' in tpl
assert '<button class="btn small primary searchapi-save-button">Save API key</button>' in tpl
assert 'AI research is supplemental and sparse.' not in tpl
assert 'name="chatgpt_auto_daily_limit" min="0" max="1000"' in tpl
assert 'name="ai_mode_auto_daily_limit" min="0" max="1000"' in tpl
assert '</form>\n<div class="searchapi-test-section">' in tpl
assert '</form>\n<hr class="soft"><div class="searchapi-test-section">' not in tpl
# Test row order remains query -> service -> action.
row_start=tpl.index('<div class="searchapi-test-row">')
row_end=tpl.index('</div></div><div id="provider-test-',row_start)
row=tpl[row_start:row_end]
assert row.index('<input') < row.index('<select') < row.index('>Test Search</button>')
# Compact test output strips markup and bounds descriptions.
assert 'function compactSearchTestText(value,maxLen=650)' in tpl
assert "replace(/<[^>]*>/g,' ')" in tpl
assert 'compactSearchTestText(x.snippet||\'\',650)' in tpl
assert 'searchapi-test-snippet' in tpl
assert 'compactSearchTestText(r.answer,1800)' in tpl

css=read('portal/static/portal/app.css')
assert '.searchapi-service-checks{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))' in css
assert '.searchapi-service-check{display:flex!important;align-items:flex-start!important' in css
assert '.searchapi-service-check span{min-width:0;white-space:normal;overflow-wrap:anywhere}' in css
assert '.searchapi-api-key-wrap{display:grid;grid-template-columns:minmax(0,1fr) auto' in css
assert '.searchapi-test-snippet' in css and '-webkit-line-clamp:4' in css
assert '.search-log-table tbody td{vertical-align:middle!important}' in css
assert '.search-log-provider-cell .provider-label-with-icon{align-items:center!important}' in css
assert '.search-log-query-wrap{align-items:center!important;min-height:22px}' in css
# Existing modal and quota pressure behavior remain.
assert '.searchapi-provider-card{width:min(920px,calc(100vw - 32px))!important;max-width:min(920px,calc(100vw - 32px))!important;max-height:88vh;overflow-y:auto;overflow-x:hidden' in css
for state,color in [('unused','#718b9c'),('healthy','#42d98b'),('warning','#e8b84f'),('critical','#ef6b73')]:
    assert f'.quota-indicator.quota-state-{state}:hover,.quota-indicator.quota-state-{state}:focus-visible{{color:{color}!important}}' in css

migration=read('portal/migrations/0209_v011137_searchapi_validation_polish.py')
assert "dependencies=[('portal','0208_v011136_searchapi_ui_cleanup')]" in migration
assert "if old in (None,10,'10'):" in migration
assert "cfg['auto_daily_limit']=100" in migration
assert "version='0.11.137'" in migration
assert "'searchapi_save_validation':True" in migration

# Missing SearchAPI credentials still stop before real dispatch/telemetry.
assert "if str(getattr(source,'name','') or '').startswith('SearchAPI ·') and not state.get('api_configured'):" in search
assert "'message':'SearchAPI API key is not configured. Save the API key before testing.'" in search

# Global coverage and re-evaluation safeguards remain.
spec=importlib.util.spec_from_file_location('v011137_discovery_markets',root/'portal/services/discovery_markets.py')
dm=importlib.util.module_from_spec(spec); sys.modules[spec.name]=dm; spec.loader.exec_module(dm)
assert len(dm.DEFAULT_MARKET_CODES)>=190
for code in ('us','gb','au','sg','hk','cn','tw','id','th','vn','ng','ke','ar','cl'):
    assert code in dm.MARKET_BY_CODE, code
of_tree=ast.parse(read('portal/services/opportunity_filter.py'))
for node in ast.walk(of_tree):
    assert not (isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.UAdd))
tasks=read('portal/tasks.py')
assert 'MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD = 3' in tasks
assert 'def _bounded_parallel_futures' in tasks

fresh=read('portal/services/fresh_sources.py')
assert 'ScoutBox/0.11.137' in fresh

print('ScoutBox 0.11.137 targeted regression checks passed')
