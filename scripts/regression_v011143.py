from pathlib import Path
import ast
import datetime as dt
import hashlib
import importlib.util
import re
import sys
from types import SimpleNamespace

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.143'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.143'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.143'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.143'
assert (root/'docs/RELEASE_NOTES_0.11.143.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-28 22:46:48'" in read('opportunity_portal/settings.py')
assert 'The release following 0.11.143 is 0.11.144' in read('RELEASE_POLICY.md')

# Load dependency-light source-domain expansion used by source-level scheduling.
spec=importlib.util.spec_from_file_location('v011141_source_domains',root/'portal/services/source_domains.py')
sd=importlib.util.module_from_spec(spec); sys.modules[spec.name]=sd; spec.loader.exec_module(sd)

queryplanner=read('portal/services/queryplanner.py')
assert 'total_limit=32' not in queryplanner
assert 'bounded-source-rotation' in queryplanner
assert 'source_coverage_max_rotations' in queryplanner
assert 'target_sources: Iterable[dict] | None = None' in queryplanner
assert '_coverage_rotation(site_rows' in queryplanner
assert 'expand_source_domains(item[\'domain\']' in queryplanner

# Execute the actual dependency-light source scheduling helpers. With 100 enabled sources
# and 30 source slots, all 100 must appear within four consecutive rotations.
tree=ast.parse(queryplanner)
keep={'_normalise','_rotation_bucket','_coverage_rotation','_source_target_rows'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in keep]
clock=SimpleNamespace(now=0.0)
clock.time=lambda: clock.now
ns={'re':re,'hashlib':hashlib,'time':clock,'expand_source_domains':sd.expand_source_domains}
mod=ast.Module(body=nodes,type_ignores=[]); ast.fix_missing_locations(mod)
exec(compile(mod,'<source-coverage>','exec'),ns,ns)

targets=[{'source_id':i+1,'source_name':f'Source {i+1}','domain':f'source{i+1}.example'} for i in range(100)]
seen=set(); interval=120; base_bucket=500000
for step in range(4):
    clock.now=(base_bucket+step)*interval*60+1
    rows=ns['_source_target_rows'](target_sources=targets,campaign_id=3,interval_minutes=interval,rotation_offset=0)
    chosen=ns['_coverage_rotation'](rows,3,interval,30,0)[:30]
    seen.update(row['source_id'] for row in chosen)
assert len(seen)==100, len(seen)

clock.now=base_bucket*interval*60+1
variant_rows=ns['_source_target_rows'](target_sources=[
    {'source_id':1,'source_name':'Indeed','domain':'indeed.com'},
    {'source_id':2,'source_name':'YC Work at a Startup','domain':'workatastartup.com'},
],campaign_id=1,interval_minutes=interval)
assert len(variant_rows)==2
assert variant_rows[0]['domain'] in sd.expand_source_domains('indeed.com',limit=6)
assert variant_rows[1]['source_domain']=='workatastartup.com'

search=read('portal/services/search.py')
assert "target_sources.append({'source_id':source.pk,'source_name':source.name,'domain':d})" in search
assert 'target_sources=target_sources' in search
assert 'ScoutBox/0.11.143' in search

fresh=read('portal/services/fresh_sources.py')
assert "'yc_jobs'" in fresh
assert "'yc_jobs':_yc_jobs" in fresh
assert 'def _yc_jobs(source, campaign, search_profile, limit):' in fresh
assert "https://www.ycombinator.com/jobs" in fresh
assert "https://www.ycombinator.com/jobs/role/all" in fresh
assert "https://www.workatastartup.com/jobs" in fresh
assert "'domains_touched':domains" in fresh
assert "selection_reason':'coverage-oldest-attempt'" not in fresh  # reasons are built dynamically, not hard-coded into metrics
assert "'coverage-oldest-attempt'" in fresh
assert 'search_fallback_sources=list(adapter_sources)' in fresh
assert "sources=[pair for pair in adapter_sources if _adapter_configured(pair[0],pair[1])]" in fresh
direct_block=fresh[fresh.index('def direct_source_rows'):fresh.index('def forum_source_rows')]
assert direct_block.index('sources=[pair for pair in adapter_sources if _adapter_configured') < direct_block.index('cap_sources=max(1,min(len(sources)')

# HN direct-page scanning must no longer own YC vacancy pages.
hn_start=fresh.index('def _hn_direct_page_rows')
hn_end=fresh.index('def _hn_whoishiring',hn_start)
hn_block=fresh[hn_start:hn_end]
assert 'https://www.ycombinator.com/jobs' not in hn_block
assert 'https://news.ycombinator.com/jobs' in hn_block

# Execute the direct-source selector with ten healthy sources. The two never-attempted
# sources must occupy the first two coverage slots even though six healthy leaders exist.
ftree=ast.parse(fresh)
fkeep={'_adaptive_source_key','_coverage_source_key','_select_direct_sources'}
fnodes=[n for n in ftree.body if isinstance(n,ast.FunctionDef) and n.name in fkeep]
fns={}
fmod=ast.Module(body=fnodes,type_ignores=[]); ast.fix_missing_locations(fmod)
exec(compile(fmod,'<direct-selection>','exec'),fns,fns)
sources=[]; efficiency={}; last={}
now=dt.datetime(2026,9,28,tzinfo=dt.timezone.utc)
for i in range(10):
    src=SimpleNamespace(pk=i+1,name=f'Source {i+1}',priority=50)
    sources.append((src,'adapter'))
    efficiency[src.pk]={'requests':50,'unique_results':10,'active_records':5,'discarded_records':0,'error_rate':0.0,'unique_per_100':20.0,'active_per_100':10.0,'retention_rate':1.0}
    if i < 8:
        last[src.name]=now-dt.timedelta(hours=i)
selected,reasons=fns['_select_direct_sources'](sources,efficiency,last,6)
assert len(selected)==6
assert {x[0].name for x in selected[:2]}=={'Source 9','Source 10'}, [x[0].name for x in selected]
assert reasons['Source 9']=='coverage-oldest-attempt' and reasons['Source 10']=='coverage-oldest-attempt'
assert sum(1 for r in reasons.values() if r=='performance')==4

# Search-engine fallback is independent of the capped direct selection and uses one
# domain-family variant per source per pass.
discovery=read('portal/services/discovery.py')
assert "get('search_fallback_sources')" in discovery
assert 'ordered[:max_queries]' in discovery
assert 'variants=expand_source_domains(domain,limit=6) or [domain]' in discovery
assert 'expanded_domain=variants[(bucket+source_index)%len(variants)]' in discovery

seed=read('portal/management/commands/seed_defaults.py')
assert "'YC Work at a Startup': {'direct_adapter':'yc_jobs'" in seed
migration=read('portal/migrations/0213_v011141_source_coverage_integrity.py')
assert "dependencies=[('portal','0212_v011140_facebook_page_identity_titles')]" in migration
assert "'direct_adapter':'yc_jobs'" in migration
assert "version='0.11.141'" in migration

# Prior 0.11.140 Facebook identity repair and 0.11.133 global market coverage remain packaged.
assert (root/'portal/migrations/0212_v011140_facebook_page_identity_titles.py').exists()
assert (root/'portal/migrations/0205_v011133_global_coverage_searchapi.py').exists()

css=read('portal/static/portal/app.css')
assert 'ScoutBox 0.11.142 — Facebook Page titles stay readable in the compact table.' in css
assert '.facebook-page-title-text{' in css
assert '-webkit-line-clamp:2!important' in css
assert 'white-space:normal!important' in css
assert 'max-height:2.7em!important' in css

current_migration=read('portal/migrations/0214_v011142_facebook_page_title_wrap.py')
assert "dependencies=[('portal','0213_v011141_source_coverage_integrity')]" in current_migration
assert "version='0.11.142'" in current_migration
assert "'facebook_page_title_two_line_wrap':True" in current_migration

tasks=read('portal/tasks.py')
reconcile=read('portal/management/commands/reconcile_worker_state.py')
assert 'def _latest_graceful_service_stop' in tasks
assert "action__in=['service_started','service_stopped']" in tasks
assert "return event if event is not None and event.action=='service_stopped' else None" in tasks
assert 'def _activity_predates_restart' in tasks
assert 'def _clear_restart_local_ai_lanes' in tasks
assert "match='scoutbox:local-ai:lane:*'" in tasks
assert 'def _recover_campaign_runs_interrupted_by_restart' in tasks
assert "'coverage_exempt':True" in tasks
assert "'interrupted_by_restart':True" in tasks
assert "'restart_recovery_of_run_id'=run.pk" not in tasks  # dict assignment is bracket syntax
assert "replacement_criteria['restart_recovery_of_run_id']=run.pk" in tasks
assert "message='Queued after ScoutBox restart'" in tasks
assert "message='Interrupted by ScoutBox restart — recovering'" in tasks
assert "if snapshot.get('available'):" in tasks
assert "restart_event=_latest_graceful_service_stop(now) if startup and not snapshot['available'] else None" in tasks
assert "state='interrupted_service_restart'" in tasks
assert 'def _run_is_coverage_exempt' in tasks
assert "criteria.get('coverage_exempt')" in tasks
assert '_primary_coverage_runs(_non_forum_runs(' in tasks
assert '_recover_campaign_runs_interrupted_by_restart(now,snapshot=snapshot)' in reconcile
assert "bg['company_research_requeued_ids']=_requeue_interrupted_company_research(bg)" in reconcile

migration143=read('portal/migrations/0215_v011143_restart_recovery.py')
assert "dependencies=[('portal','0214_v011142_facebook_page_title_wrap')]" in migration143
assert "version='0.11.143'" in migration143
assert "'restart_interrupted_campaign_recovery':True" in migration143
assert "'restart_stale_local_ai_lock_cleanup':True" in migration143

# Pure restart-boundary logic is easy to exercise without Django/Redis.
tree=ast.parse(tasks)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_activity_predates_restart')
class TZ:
    @staticmethod
    def is_naive(value): return value.tzinfo is None
    @staticmethod
    def make_aware(value, zone): return value.replace(tzinfo=zone)
    @staticmethod
    def get_current_timezone(): return dt.timezone.utc
ns2={'timezone':TZ,'timedelta':dt.timedelta}
mod2=ast.Module(body=[node],type_ignores=[]); ast.fix_missing_locations(mod2)
exec(compile(mod2,'<restart-boundary>','exec'),ns2,ns2)
stop=dt.datetime(2026,9,28,14,28,0,tzinfo=dt.timezone.utc)
assert ns2['_activity_predates_restart'](stop-dt.timedelta(seconds=2),stop)
assert ns2['_activity_predates_restart'](stop+dt.timedelta(seconds=20),stop)
assert not ns2['_activity_predates_restart'](stop+dt.timedelta(seconds=31),stop)

assert (root/'portal/tests/test_v011143.py').exists()
print('ScoutBox 0.11.143 targeted regression checks passed')
