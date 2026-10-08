from pathlib import Path
import ast
import importlib.util
import sys
from types import SimpleNamespace

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.134'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.134'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.134'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.134'
assert (root/'docs/RELEASE_NOTES_0.11.134.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-28 13:11:00'" in read('opportunity_portal/settings.py')

# Preserve the 0.11.133 worldwide catalogue and acquisition-fair scheduler.
spec=importlib.util.spec_from_file_location('v011134_discovery_markets',root/'portal/services/discovery_markets.py')
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

search=read('portal/services/search.py')
for name in ('SearchAPI · Google Jobs','SearchAPI · Google Web','SearchAPI · Google Forums','SearchAPI · Google News'):
    assert name in search
assert search.count("'shared_credential_group':'searchapi'")>=4
assert search.count("'shared_budget_group':'searchapi'")>=4
assert "if not bool((source.config_json or {}).get('supplemental_only'))" in search
assert "name__startswith='SearchAPI ·'" in search
assert "def provider_budget_used(source):" in search
assert "return max(0,provider_budget(source)-provider_budget_used(source))" in search
assert "raise RuntimeError('SearchAPI requires an explicit Discovery Market" in search
assert "def search_searchapi_google_forums" in search and "'google_forums'" in search
assert "'time_period':'last_month'" in search and "'safe':'active'" in search and "'link':'resolved'" in search
assert "def search_searchapi_google_news" in search and "'google_news'" in search
assert "'sort_by':'most_recent'" in search
assert "'_community_hiring_signal':True" in search
assert "'_news_signal':True,'_signal_only':True" in search
assert "elif source.name=='SearchAPI · Google Forums'" in search
assert "elif source.name=='SearchAPI · Google News'" in search

# Execute the dependency-light SearchAPI signal parser: Forum rows are community evidence;
# News rows are signal-only and can never directly become Opportunity rows.
search_tree=ast.parse(search)
signal_node=next(n for n in search_tree.body if isinstance(n,ast.FunctionDef) and n.name=='_searchapi_signal_rows')
def _normalise_result(title,url,snippet): return {'title':str(title),'url':str(url),'snippet':str(snippet)}
signal_ns={'_normalise_result':_normalise_result,'unwrap_search_result_url':lambda u:u,'is_search_engine_url':lambda u:'google.com/search' in str(u)}
exec(compile(ast.fix_missing_locations(ast.Module(body=[signal_node],type_ignores=[])),'<signal-parser>','exec'),signal_ns)
forum=signal_ns['_searchapi_signal_rows']({'organic_results':[{'title':'Acme is hiring firmware engineers','link':'https://www.reddit.com/r/embedded/x','source':'Reddit · r/embedded','domain':'reddit.com','date':'2 days ago','snippet':'Acme is hiring engineers for embedded Linux and device firmware.'}]},10,adapter='searchapi_google_forums',acquisition_path='forums',forum=True)
assert len(forum)==1 and forum[0]['_community_hiring_signal'] is True and forum[0]['_forum_source'] is True
assert not forum[0].get('_signal_only')
news=signal_ns['_searchapi_signal_rows']({'organic_results':[{'title':'Acme expands Singapore engineering team','link':'https://example.test/news/acme','source':'Example News','domain':'example.test','date':'today','snippet':'Acme plans to hire 50 embedded and systems engineers in Singapore.'}]},10,adapter='searchapi_google_news',acquisition_path='news',news=True)
assert len(news)==1 and news[0]['_news_signal'] is True and news[0]['_signal_only'] is True

fresh=read('portal/services/fresh_sources.py')
assert "if adapter in {'hn_whoishiring','reddit','lobsters_jobs','dev_hiring','indiehackers_jobs',FORUM_DIRECT_ADAPTER}:" in fresh
assert "clean['_community_hiring_signal']=True" in fresh
assert "row['_community_kind']='hacker_news_hiring'" in fresh
assert 'ScoutBox/0.11.134 community hiring-signal discovery' in fresh

discovery=read('portal/services/discovery.py')
assert 'research_hiring_signal' in discovery
assert "if candidate.get('_community_hiring_signal'):" in discovery
assert "researched['_cloud_community_signal']=True" in discovery
assert "researched['_cloud_community_signal_review']=signal_review" in discovery
assert "if result.get('_cloud_community_signal') and cloud_signal_review:" in discovery
assert "_capture_community_hiring_signal(" in discovery
assert "if result.get('_community_hiring_signal') or result.get('_structured_signal_evidence') or result.get('_news_signal'):\n        return [record]" in discovery
assert "and not community_signal" in discovery
assert "if mode=='source_guided':" in discovery and "'searchapi_forums':forum_signal_meta" in discovery
assert "include_news=False,forum_only=True" in discovery
assert "SearchAPI · Google Forums" in discovery and "SearchAPI · Google News" in discovery
assert "'qualification_lane':('cloud_web' if result.get('_cloud_community_signal') else 'local_ai')" in discovery
assert "state['cloud_signal_qualification']=local_review" in discovery
assert "supplemental: they cannot displace Google Jobs/Web" in discovery
# 0.11.133 market-specific regional board path remains.
assert "market_provider=next((p for p in providers if p.name=='SearchAPI · Google Web'),None)" in discovery
assert "SCOUTBOX_MARKET_SOURCE_QUERIES_PER_RUN" in discovery
assert "multilingual_language,translation_source=_translation_language_for_result" in discovery

cloud=read('portal/services/cloud_discovery.py')
assert "def research_hiring_signal(campaign, candidate, page_text='', anchor=None):" in cloud
assert 'A canonical vacancy URL is NOT required for a Hidden Lead.' in cloud
assert "bundled_activities=['community hiring-signal verification']" in cloud
assert "purpose not in {'company_hiring_signal','company_outreach_target','job_opportunity','contract_project','other'}" in cloud
assert "confidence < 60 or relevance < 55" in cloud

mig=read('portal/migrations/0206_v011134_community_searchapi_signals.py')
assert "dependencies = [('portal', '0205_v011133_global_coverage_searchapi')]" in mig
assert "category='SearchAPI Discovery'" in mig
assert "name='SearchAPI · Google Forums'" in mig and "name='SearchAPI · Google News'" in mig
assert "'supplemental_only':True" in mig
assert "'signal_mode':'community'" in mig and "'signal_mode':'news'" in mig
assert "version='0.11.134'" in mig

# Search Sources quota UI counts the shared SearchAPI account once rather than once/engine.
views=read('portal/views.py')
assert 'provider_budget_used' in views
assert "quota_groups_seen=set()" in views
assert "provider_label=('SearchAPI shared pool' if quota_group=='searchapi' else source.name)" in views

# 0.11.132 execution/layout guardrails remain intact.
css=read('portal/static/portal/app.css')
assert '.portal-choice-card{width:min(980px,calc(100vw - 32px))!important;max-width:min(980px,calc(100vw - 32px))!important}' in css
of_source=read('portal/services/opportunity_filter.py')
of_tree=ast.parse(of_source)
for node in ast.walk(of_tree):
    assert not (isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.UAdd)), 'unexpected unary + in opportunity_filter.py'
tasks=read('portal/tasks.py')
assert 'MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD = 3' in tasks
assert 'def _bounded_parallel_futures' in tasks

print('ScoutBox 0.11.134 targeted regression checks passed')
