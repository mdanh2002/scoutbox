from pathlib import Path
import ast
import concurrent.futures
import importlib.util
import json
import sys
from types import SimpleNamespace

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.133'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.133'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.133'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.133'
assert (root/'docs/RELEASE_NOTES_0.11.133.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-28 12:04:00'" in read('opportunity_portal/settings.py')

# Load the dependency-light market module directly. This exercises the real catalogue and
# scheduler without requiring a Django installation or database in the release verifier.
spec=importlib.util.spec_from_file_location('v011133_discovery_markets',root/'portal/services/discovery_markets.py')
dm=importlib.util.module_from_spec(spec); sys.modules[spec.name]=dm; spec.loader.exec_module(dm)
assert len(dm.DEFAULT_MARKET_CODES)>=190
for code in ('us','gb','au','sg','hk','cn','tw','id','th','vn','ng','ke','ar','cl'):
    assert code in dm.MARKET_BY_CODE, code
assert len(dm.DEFAULT_MARKET_CODES)==len(set(dm.DEFAULT_MARKET_CODES))
assert dm.MARKET_BY_CODE['pe'].languages[0]=='Spanish'
assert dm.MARKET_BY_CODE['sn'].languages[0]=='French'
assert dm.MARKET_BY_CODE['ao'].languages[0]=='Portuguese'
assert dm.MARKET_BY_CODE['jo'].languages[0]=='Arabic'

cfg=SimpleNamespace(discovery_markets=['us','gb','au','sg','hk','id','vn'],discovery_market_strategy='global')
evidence={'us':{'attempts':100},'gb':{'attempts':40},'au':{'attempts':30},'sg':{'attempts':20},'hk':{'attempts':10},'id':{'attempts':0},'vn':{'attempts':0}}
plan=dm.market_plan(cfg,campaign_id=2,rotation_offset=0,evidence=evidence)
assert plan['effective_strategy']=='global'
assert plan['ordered_codes'].index('id') < plan['ordered_codes'].index('us')
assert plan['ordered_codes'].index('vn') < plan['ordered_codes'].index('us')
schedule=dm.market_workload_schedule(plan,7,rotation_offset=0)
assert len(schedule)==len({m.code for m in schedule})
assert any(m.code in {'us','gb','au','sg','hk'} for m in schedule)
deficit_plan=dm.market_plan(SimpleNamespace(discovery_markets=['us','gb','id','vn'],discovery_market_strategy='global'),campaign_id=5,rotation_offset=3,evidence={'us':{'attempts':100},'gb':{'attempts':80},'id':{'attempts':0},'vn':{'attempts':1}})
deficit_schedule=dm.market_workload_schedule(deficit_plan,2,rotation_offset=3)
assert [m.code for m in deficit_schedule]==['id','vn']
assert dm.multilingual_strength_cap(SimpleNamespace(multilingual_exploration_strength='balanced',discovery_markets=dm.DEFAULT_MARKET_CODES))==16
multi_cfg=SimpleNamespace(multilingual_exploration_strength='high',multilingual_languages=[])
multi_markets=[dm.MARKET_BY_CODE[x] for x in ('es','mx','ar','cl','fr','be')]
a0=dm.multilingual_assignments(multi_cfg,multi_markets,rotation_offset=0)
a1=dm.multilingual_assignments(multi_cfg,multi_markets,rotation_offset=1)
spanish0=[x['market'].code for x in a0 if x['language']=='Spanish']
spanish1=[x['market'].code for x in a1 if x['language']=='Spanish']
assert len(spanish0)>=3 and spanish0[0]!=spanish1[0]

models=read('portal/models.py')
assert "discovery_market_strategy = models.CharField(max_length=20, default='global'" in models
assert "('global','Global Coverage')" in models
views=read('portal/views.py')
assert "strategy=(request.POST.get('discovery_market_strategy') or 'global')" in views

# SearchAPI is a Search Source with two logical engines that share one credential and
# reject missing/Worldwide market context instead of allowing Google's implicit US default.
search=read('portal/services/search.py')
for name in ('SearchAPI · Google Jobs','SearchAPI · Google Web'):
    assert name in search
assert "'env_key':'SEARCHAPI_API_KEY'" in search
assert search.count("'shared_credential_group':'searchapi'")>=2
assert "SEARCHAPI_ENDPOINT='https://www.searchapi.io/api/v1/search'" in search
assert "raise RuntimeError('SearchAPI requires an explicit Discovery Market" in search
assert "if name.startswith('SearchAPI ·') and code=='worldwide':" in search
assert "params={'gl':str(meta.get('country_code') or '').strip().lower(),'hl':language}" in search
assert "params['location']=location" in search
assert "'Authorization':f'Bearer {key}'" in search
assert "Do not force Google's document-language restriction" in search
assert "retry.pop('gl',None)" in search and "active_params.get('location')" in search
assert "def _searchapi_error_message(data):" in search
assert "def _searchapi_apply_link(item):" in search
assert "'_direct_adapter':'searchapi_google_jobs'" in search
assert "'_role_location_hint':location[:800]" in search
assert "for reserved_name in ('SearchAPI · Google Jobs','SearchAPI · Google Web')" in search

# Execute the locale helper itself with a tiny stub, covering the no-US-default invariant.
search_tree=ast.parse(search)
locale_node=next(n for n in search_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_searchapi_locale')
locale_ns={'market_search_meta':lambda m:{'market_code':getattr(m,'code',''),'locale':getattr(m,'locale',''),'country_code':getattr(m,'country_code','')}}
exec(compile(ast.fix_missing_locations(ast.Module(body=[locale_node],type_ignores=[])),'<searchapi-locale>','exec'),locale_ns)
try:
    locale_ns['_searchapi_locale'](None)
except RuntimeError:
    pass
else:
    raise AssertionError('SearchAPI locale accepted missing market')
assert locale_ns['_searchapi_locale'](dm.MARKET_BY_CODE['au'])=={'gl':'au','hl':'en','location':'Australia'}
cn=locale_ns['_searchapi_locale'](dm.MARKET_BY_CODE['cn'])
assert cn['gl']=='cn' and cn['hl']=='zh-cn' and cn['location']=='China'

apply_node=next(n for n in search_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_searchapi_apply_link')
parser_node=next(n for n in search_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_searchapi_job_rows')
def _normalise_result(title,url,snippet): return {'title':str(title),'url':str(url),'snippet':str(snippet)}
import urllib.parse
parser_ns={
    '_normalise_result':_normalise_result,
    'unwrap_search_result_url':lambda u:u,
    'is_search_engine_url':lambda u:'google.com/search' in str(u),
    'urllib':urllib,
}
exec(compile(ast.fix_missing_locations(ast.Module(body=[apply_node,parser_node],type_ignores=[])),'<searchapi-job-parser>','exec'),parser_ns)
rows=parser_ns['_searchapi_job_rows']({'jobs':[{
    'title':'Firmware Engineer','company_name':'Example','location':'Singapore',
    'description':'Build embedded production firmware and low-level device software. '*4,
    'extensions':['Full-time','2 days ago'],'apply_link':'https://example.test/careers/firmware-123',
    'apply_links':[{'source':'Example Careers','link':'https://example.test/careers/firmware-123'}],
    'via':'Example Careers',
}]},10)
assert len(rows)==1 and rows[0]['_direct_source'] is True
assert rows[0]['_role_location_hint']=='Singapore' and rows[0]['company']=='Example'
link,source=parser_ns['_searchapi_apply_link']({
    'apply_link':'https://www.linkedin.com/jobs/view/123',
    'apply_links':[
        {'source':'LinkedIn','link':'https://www.linkedin.com/jobs/view/123'},
        {'source':'Example Careers','link':'https://boards.greenhouse.io/example/jobs/456'},
    ],
})
assert link=='https://boards.greenhouse.io/example/jobs/456' and source=='Example Careers'

# Execute the SearchAPI request retry invariant without network or Django. A Jobs-only gl
# rejection may remove gl, but concrete market location and language must survive.
error_node=next(n for n in search_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_searchapi_error_message')
request_node=next(n for n in search_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_searchapi_request')
class FakeHTTPError(Exception): pass
class FakeResponse:
    def __init__(self,status,data):
        self.status_code=status; self._data=data; self.ok=200 <= status < 300
        self.text=json.dumps(data); self.content=self.text.encode()
    def json(self): return self._data
    def raise_for_status(self):
        if not self.ok: raise FakeHTTPError(f'{self.status_code} error')
class FakeRequests:
    RequestException=FakeHTTPError
    def __init__(self): self.calls=[]
    def get(self,url,params=None,headers=None,timeout=None):
        self.calls.append(dict(params or {}))
        if len(self.calls)==1: return FakeResponse(400,{'error':{'message':'Unsupported gl country value'}})
        return FakeResponse(200,{'jobs':[],'search_metadata':{'status':'Success'}})
fake_requests=FakeRequests()
request_ns={
    '_provider_secret':lambda source,cap:'secret', 'provider_capability':lambda source:{},
    '_searchapi_locale':lambda market:{'gl':'au','hl':'en','location':'Australia'},
    'requests':fake_requests, 'SEARCHAPI_ENDPOINT':'https://www.searchapi.io/api/v1/search', 'UA':'ScoutBox-test',
}
exec(compile(ast.fix_missing_locations(ast.Module(body=[error_node,request_node],type_ignores=[])),'<searchapi-request>','exec'),request_ns)
data,_=request_ns['_searchapi_request'](SimpleNamespace(name='SearchAPI · Google Jobs'),'google_jobs','firmware engineer',market=object())
assert data.get('jobs')==[] and len(fake_requests.calls)==2
assert fake_requests.calls[0]['gl']=='au'
assert 'gl' not in fake_requests.calls[1]
assert fake_requests.calls[1]['location']=='Australia' and fake_requests.calls[1]['hl']=='en'
assert 'lr' not in fake_requests.calls[1]

# Global-source fallback stays on ordinary providers; market-specific board searches prefer
# SearchAPI Google Web and carry an auditable bounded market-location hint.
discovery=read('portal/services/discovery.py')
assert "generic_provider=next((p for p in providers if not p.name.startswith('SearchAPI ·')),None)" in discovery
assert "market_provider=next((p for p in providers if p.name=='SearchAPI · Google Web'),None)" in discovery
assert "SCOUTBOX_MARKET_SOURCE_QUERIES_PER_RUN" in discovery
assert "provider_query_cap=min(provider_query_cap,max(0,int(provider_budget_remaining(provider))))" in discovery
assert "result['_market_location_hint']=(item.get('market') or {}).get('market','')" in discovery
assert "multilingual_language,translation_source=_translation_language_for_result" in discovery
assert "multilingual_translation_failed" in discovery
assert "page_text=interpretation[:45000]" in discovery
assert "if result.get('_direct_source') and not inspected.get('ok')" in discovery
assert "int(inspected.get('http_status') or 0) not in (404,410)" in discovery

# Country resolution must use the bounded local-board market fallback before broad inference.
location=read('portal/services/location.py')
assert "market_location_hint=''" in location
market_pos=location.index("source='discovery_market_source_fallback'")
infer_pos=location.index("country=infer_country(target_url")
assert market_pos < infer_pos
assert "fallback=True" in location[market_pos:infer_pos]

# Upgrade migration installs SearchAPI, expands only the previous full default market set,
# switches old Balanced defaults to Global Coverage, and conservatively repairs obvious
# false-US/blank local-board countries.
mig=read('portal/migrations/0205_v011133_global_coverage_searchapi.py')
assert "dependencies = [('portal', '0204_v011132_reevaluation_reliability')]" in mig
assert "name='SearchAPI · Google Jobs'" in mig and "name='SearchAPI · Google Web'" in mig
assert "PortalSettings.objects.filter(discovery_market_strategy='balanced').update(discovery_market_strategy='global')" in mig
assert "legacy_set.issubset(set(current))" in mig
mig_tree=ast.parse(mig)
expanded=None
for node in ast.walk(mig_tree):
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expanded_default_codes' for t in node.targets):
        expanded=ast.literal_eval(node.value); break
assert expanded==dm.DEFAULT_MARKET_CODES
for marker in ("'hk.jobsdb.com':'Hong Kong'", "'sg.jobstreet.com':'Singapore'", "'seek.com.au':'Australia'", "'reed.co.uk':'United Kingdom'"):
    assert marker in mig
assert "str(getattr(opportunity, 'country', '') or '').strip() not in {'', 'United States'}" in mig
assert "version='0.11.133'" in mig

# Sources UI exposes the new strategy and does not imply an irrelevant public fallback for
# API-only SearchAPI providers.
sources=read('templates/portal/sources.html')
assert '>Global Coverage</option>' in sources
assert 'Global Coverage prioritizes markets' in sources
assert 'provider_public_fallback' in sources or 'public_fallback' in sources

# 0.11.132 re-evaluation scope and execution guardrails remain intact.
css=read('portal/static/portal/app.css')
assert '.portal-choice-card{width:min(980px,calc(100vw - 32px))!important;max-width:min(980px,calc(100vw - 32px))!important}' in css
assert '.portal-confirm-card,.binary-confirm-card{width:min(520px,calc(100vw - 32px))!important' in css
of_source=read('portal/services/opportunity_filter.py')
of_tree=ast.parse(of_source)
for node in ast.walk(of_tree):
    assert not (isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.UAdd)), 'unexpected unary + in opportunity_filter.py'

tasks=read('portal/tasks.py')
assert 'MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD = 3' in tasks
assert 'def _bounded_parallel_futures' in tasks
assert tasks.count('_bounded_parallel_futures(pool,worker,ids,MANUAL_FILTER_CLOUD_PARALLELISM)')==3
assert "'kind':'repeated_internal_error'" in tasks
assert "'kind':'empty_response'" in tasks

print('ScoutBox 0.11.133 targeted regression checks passed')
