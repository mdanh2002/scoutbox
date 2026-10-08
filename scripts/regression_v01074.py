#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')

def fail(msg):
    raise SystemExit('FAIL: '+msg)

if read('VERSION').strip()!='0.10.74': fail('VERSION is not 0.10.74')
if read('RELEASE_ID').strip()!='ScoutBox v0.10.74': fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip()!='ScoutBox v0.10.74': fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.74'): fail('README not bumped')
if not (ROOT/'docs'/'RELEASE_NOTES_0.10.74.md').is_file(): fail('0.10.74 release notes missing')

queryplanner=read('portal/services/queryplanner.py')
for token in ['def _normalize_site_constraint', 'site:facebook.com/posts', 'path-scoped site operators']:
    if token == 'site:facebook.com/posts':
        continue
    if token not in queryplanner:
        fail(f'missing query sanitizer token: {token}')
if "return 'site:'+host" not in queryplanner:
    fail('site: sanitizer does not collapse to host-only')

search=read('portal/services/search.py')
if 'site:facebook.com/posts' in search:
    fail('facebook_index_queries still emits site:facebook.com/posts')
if 'site:facebook.com/groups' in search:
    fail('facebook_index_queries still emits path-scoped site:facebook.com/groups')
if "f'site:facebook.com {base_query}'" not in search:
    fail('facebook_index_queries no longer emits host-only facebook query')

fresh=read('portal/services/fresh_sources.py')
if '(hiring OR' in fresh or 'job OR remote' in fresh or 'q=f\'({query})' in fresh:
    fail('fresh sources still contain Boolean-bundled queries')
if 'adapter=\'reddit\',max_queries=10,include_intent=True' not in fresh:
    fail('reddit still not using split rotated query variants')

discovery=read('portal/services/discovery.py')
for token in ['def _run_forum_only_campaign', 'Forum browsing only', 'forum_only=False', 'return _run_forum_only_campaign', 'SCOUTBOX_LOCAL_SEARCH_STAGE_MAX_SECONDS', 'SCOUTBOX_SEARCH_PROVIDER_STAGE_MAX_SECONDS']:
    if token not in discovery:
        fail(f'missing forum-only discovery token: {token}')
if '"paid help" OR "paid project"' in discovery or 'careers OR jobs OR hiring' in discovery:
    fail('discovery still has OR-heavy query strings')

tasks=read('portal/tasks.py')
for token in ['def _enabled_forum_discovery_sources', 'def _run_is_forum_only', "run_kind='forum_only'", 'Automatic Forum browse', 'SCOUTBOX_FORUM_BROWSE_INTERVAL_MINUTES', 'SCOUTBOX_FORUM_BROWSE_INFLIGHT_LIMIT', 'forum_only=forum_only']:
    if token not in tasks:
        fail(f'missing independent forum scheduler token: {token}')
if "CampaignRun.objects.filter(status__in=['queued','running','stopping']).count()" in tasks:
    fail('normal discovery inflight count still includes forum-only runs')
if "_active_campaign_blocker(c,now)" in tasks:
    fail('scheduler still uses all-run blocker for normal discovery')

migration=ROOT/'portal'/'migrations'/'0105_v01074_independent_forum_browse.py'
if not migration.is_file(): fail('0.10.74 migration missing')
if 'independent Forum browse scheduler repair' not in migration.read_text(encoding='utf-8'):
    fail('0.10.74 migration message missing')

# Generated web/forum/reddit queries must not reintroduce Boolean contaminants.
for rel in ['portal/services/fresh_sources.py','portal/services/forum_sources.py','portal/services/discovery.py','portal/services/search.py']:
    text=read(rel)
    for bad in ['(hiring OR','job OR remote','careers OR jobs','"paid help" OR','site:facebook.com/posts','site:facebook.com/groups']:
        if bad in text:
            fail(f'{rel} still contains query contaminant {bad!r}')

print('ScoutBox 0.10.74 targeted regressions passed.')
