from pathlib import Path
import ast
import importlib.util
import sys

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.138'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.138'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.138'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.138'
assert (root/'docs/RELEASE_NOTES_0.11.138.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-28 18:30:00'" in read('opportunity_portal/settings.py')

search=read('portal/services/search.py')
assert 'ScoutBox/0.11.138' in search
assert "SEARCHAPI_ACCOUNT_ENDPOINT='https://www.searchapi.io/api/v1/me'" in search
assert 'def validate_searchapi_credential(source, api_key=None, timeout=10):' in search
assert "status==401 or (status in (400,403,422) and auth_message)" in search
validator=search[search.index('def validate_searchapi_credential('):search.index('\n\ndef _searchapi_request',search.index('def validate_searchapi_credential('))]
assert 'SEARCHAPI_ACCOUNT_ENDPOINT' in validator
assert "'engine':'google'" not in validator
assert '_record(' not in validator and 'UsageMetric' not in validator and 'AIRequestLog' not in validator
assert "return {'status':'valid','ok':True" in validator
assert "return {'status':'invalid','ok':False" in validator
assert "return {'status':'unavailable','ok':False" in validator

# Exercise Account API validation classification without importing Django.
tree=ast.parse(search)
nodes=[]
for name in ('_searchapi_error_message','_searchapi_auth_rejected','validate_searchapi_credential'):
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
ns={
    'SEARCHAPI_ACCOUNT_ENDPOINT':'https://example.invalid/api/v1/me',
    'UA':'ScoutBox test',
    'provider_capability':lambda s:{},
    '_provider_secret':lambda s,c:'saved-key',
}
ns['requests']=RequestsStub(Resp(200,{'account':{'remaining_credits':100},'api_usage':{'searches_this_hour':1}}))
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<validator>','exec'),ns)
assert ns['validate_searchapi_credential'](object())['status']=='valid'
ns['requests']=RequestsStub(Resp(401,{'error':{'message':'Invalid API key'}},'Invalid API key'))
assert ns['validate_searchapi_credential'](object())['status']=='invalid'
ns['requests']=RequestsStub(exc=Exception('offline'))
assert ns['validate_searchapi_credential'](object())['status']=='unavailable'

# Regression for the 0.11.137 Forums/News/Local auth bug: engine parameters must not
# reuse/overwrite the variable that holds the API key.
request_fn=search[search.index('def _searchapi_request('):search.index('\n\ndef _searchapi_apply_link',search.index('def _searchapi_request('))]
assert 'for param_name,param_value in dict(extra_params or {}).items():' in request_fn
assert 'params[str(param_name)]=param_value' in request_fn
assert 'for key,value in dict(extra_params or {}).items():' not in request_fn
assert "headers={'Authorization':f'Bearer {key}'" in request_fn
assert '_mark_searchapi_authenticated_success' in request_fn
assert "_set_searchapi_validation_state('invalid'" in request_fn

# Shared SearchAPI credential must prefer the unified hub, not a stale child secret.
secret_fn=search[search.index('def _provider_secret('):search.index('\ndef _provider_extra',search.index('def _provider_secret('))]
assert "if cap.get('shared_credential_group')=='searchapi':" in secret_fn
assert 'hub=searchapi_master_source()' in secret_fn
assert 'return master' in secret_fn

views=read('portal/views.py')
assert "SearchSource.objects.filter(name__startswith='SearchAPI ·').exclude(pk=source.pk).update(api_key_enc='')" in views
assert "SearchSource.objects.filter(name__startswith='SearchAPI ·').update(api_key_enc='')" in views
assert 'validation=validate_searchapi_credential(source)' in views
assert 'SearchAPI API key saved and validated.' in views
assert 'any successful SearchAPI request will confirm it automatically.' in views

migration=read('portal/migrations/0210_v011138_searchapi_credential_reliability.py')
assert "dependencies=[('portal','0209_v011137_searchapi_validation_polish')]" in migration
assert "name='SearchAPI · Google Jobs'" in migration
assert ".exclude(pk=hub.pk).update(api_key_enc='')" in migration
assert "version='0.11.138'" in migration
assert "'searchapi_extra_param_auth_shadow_fix':True" in migration

# Keep all major 0.11.137 UI and routing behavior.
tpl=read('templates/portal/sources.html')
assert '<button class="btn small primary searchapi-save-button">Save API key</button>' in tpl
assert 'searchapi-service-checks' in tpl
assert '>Test Search</button>' in tpl
assert 'compactSearchTestText(x.snippet||\'\',650)' in tpl
css=read('portal/static/portal/app.css')
assert '.searchapi-service-checks{display:grid!important' in css
assert '.search-log-table tbody td{vertical-align:middle!important}' in css
for state,color in [('unused','#718b9c'),('healthy','#42d98b'),('warning','#e8b84f'),('critical','#ef6b73')]:
    assert f'.quota-indicator.quota-state-{state}:hover,.quota-indicator.quota-state-{state}:focus-visible{{color:{color}!important}}' in css
assert "return max(0,min(10000,int(getattr(cfg,'searchapi_daily_limit',500))))" in search
assert "default_limit=100 if service in {'chatgpt','ai_mode'} else 0" in search

# Global coverage and re-evaluation safeguards remain.
spec=importlib.util.spec_from_file_location('v011138_discovery_markets',root/'portal/services/discovery_markets.py')
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
assert 'ScoutBox/0.11.138' in fresh

print('ScoutBox 0.11.138 targeted regression checks passed')
