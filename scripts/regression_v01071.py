#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')

def fail(msg):
    raise SystemExit('FAIL: '+msg)

if read('VERSION').strip()!='0.10.71':
    fail('VERSION is not 0.10.71')
if read('RELEASE_ID').strip()!='ScoutBox v0.10.71':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip()!='ScoutBox v0.10.71':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.71'):
    fail('README not bumped')
if not (ROOT/'docs'/'RELEASE_NOTES_0.10.71.md').is_file():
    fail('0.10.71 release notes missing')

fresh=read('portal/services/fresh_sources.py')
for token in ['import threading', 'from django.db import close_old_connections', 'def _run_adapter_with_liveness', 'progress_callback=None', 'should_stop=None']:
    if token not in fresh:
        fail(f'missing direct/forum liveness token: {token}')
if 'ADAPTER_FUNCTIONS[adapter](source,campaign,search_profile,per_source)' in fresh:
    fail('direct_source_rows still calls adapters without liveness wrapper')
if '[:24]' in fresh.split('def _direct_query_variants',1)[1].split('def _merge_rows_unique',1)[0]:
    fail('direct query variants are still capped to first 24 skills')
for token in ['cv_terms', 'preferred_terms', 'profile-tech', 'CV-specific']:
    if token not in fresh:
        fail(f'direct query planner missing broader CV/profile coverage token: {token}')
if 'timeout=forum_timeout' not in fresh:
    fail('forum fetches do not use bounded forum timeout')

discovery=read('portal/services/discovery.py')
for token in ['forum_source_rows(campaign,direct_search_profile,limit=forum_limit,test=test,progress_callback=progress_callback,should_stop=should_stop)', "forum_source_rows(campaign,plan.get('search_profile') or {},limit=forum_limit,test=test,progress_callback=progress_callback,should_stop=should_stop)"]:
    if token not in discovery:
        fail('campaign runner does not pass progress/stop callbacks to forum browsing')

planner=read('portal/services/queryplanner.py')
for token in ['CV_TECH_LEXICON', "'.NET'", "'C#'", "'VoIP'", "'Asterisk'", 'return rows[:80]', 'cv_terms_all', 'rotate_plain', 'term_pool=[]']:
    if token not in planner:
        fail(f'query planner missing CV technology rotation token: {token}')
if 'cv_terms=[x[\'term\'] for x in skills if x.get(\'sources\',{}).get(\'cv\')][:18]' in planner:
    fail('source-guided query planner still uses old first-18 CV cap')

base=read('templates/portal/base.html')
for token in ['async exportDocx(){', "chatbot_export", "JSON.stringify({transcript})"]:
    if token not in base:
        fail(f'chat export missing token: {token}')

about=read('templates/portal/about.html')
if "<span>Discovery Mode</span>" not in about or "{% icon 'runtime_cloud' %}</span><span>Discovery Mode</span>" not in about:
    fail('About ScoutBox Discovery Mode icon not updated')
if about.count("{% icon 'search' %}") != 1:
    fail('About ScoutBox repeats search icon')

migration=ROOT/'portal'/'migrations'/'0103_v01071_forum_heartbeat_release.py'
if not migration.is_file():
    fail('stale forum run release migration missing')
if 'Released stale Forum browsing run' not in migration.read_text(encoding='utf-8'):
    fail('stale forum run migration message missing')

print('ScoutBox 0.10.71 targeted regressions passed.')
