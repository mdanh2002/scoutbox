#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')

def fail(msg):
    raise SystemExit('FAIL: '+msg)

if read('VERSION').strip()!='0.10.70':
    fail('VERSION is not 0.10.70')
if read('RELEASE_ID').strip()!='ScoutBox v0.10.70':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip()!='ScoutBox v0.10.70':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.70'):
    fail('README not bumped')
if not (ROOT/'docs'/'RELEASE_NOTES_0.10.70.md').is_file():
    fail('0.10.70 release notes missing')

fresh=read('portal/services/fresh_sources.py')
for token in ['def _direct_query_variants', 'def _merge_rows_unique', "adapter='reddit'", "adapter='himalayas'", "adapter='linkedin_job_library'", "adapter='glassdoor_jobs'"]:
    if token not in fresh:
        fail(f'missing direct source query planner token: {token}')
if "q=f'({query}) (hiring OR job OR remote OR contract OR freelance OR \"paid help\")'" not in fresh:
    fail('Reddit direct adapter does not use varied rotated query terms')
if "params={'limit':100,'offset':0}" not in fresh:
    fail('SmartRecruiters no longer browses company boards first')
if "'_direct_query':query" not in fresh and "'_direct_query':q" not in fresh:
    fail('direct query provenance missing')
if "'query':str(query or '')" not in fresh:
    fail('network metric query metadata missing')
if "'query':('; '.join(queries[:6]))" not in fresh:
    fail('adapter result query aggregation missing')

mail=read('portal/services/mailbox.py')
if "SCOUTBOX_VERBOSE_ADDRESSBOOK_PROMOTION_AUDIT" not in mail:
    fail('verbose addressbook promotion audit switch missing')
if "if outcome not in {'created','updated'}:" not in mail:
    fail('noisy addressbook skipped promotion logs are not suppressed')

views=read('portal/views.py')
if "Forum browse" not in views or "forum URLs checked" not in views:
    fail('forum browsing details are not exposed in Search Activity')

extras=read('portal/templatetags/portal_extras.py')
if 'def latency_human' not in extras or "{n/1000.0:.1f} sec" not in extras:
    fail('latency_human filter missing seconds display')
search_log=read('templates/portal/search_log.html')
if '{{x.latency_ms|latency_human}}' not in search_log:
    fail('Search Activity does not use latency_human')

print('ScoutBox 0.10.70 targeted regressions passed.')
