#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')

def fail(msg):
    raise SystemExit('FAIL: '+msg)

if read('VERSION').strip()!='0.10.73': fail('VERSION is not 0.10.73')
if read('RELEASE_ID').strip()!='ScoutBox v0.10.73': fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip()!='ScoutBox v0.10.73': fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.73'): fail('README not bumped')
if not (ROOT/'docs'/'RELEASE_NOTES_0.10.73.md').is_file(): fail('0.10.73 release notes missing')

fresh=read('portal/services/fresh_sources.py')
if "(hiring OR job OR remote OR contract" in fresh or "q=f'({query})" in fresh:
    fail('Reddit still builds parenthesized OR bundle')
for token in ["adapter='reddit',max_queries=10,include_intent=True", "re.sub(r'\\b[oO][rR]\\b'", 'Forum browsing time budget reached', 'forum-sources', 'progress_message=(f\'Browsing forum sources: {source.name} ({source_index}/{total_sources})']:
    if token not in fresh:
        fail(f'missing direct/forum query or stall token: {token}')
if 'forum_listing_urls(base,software,cfg,source.name)[:2]' not in fresh:
    fail('forum adapter still tries too many listing URLs per source')
if 'max(1,min(2,int(limit or 12)))' not in fresh:
    fail('forum native fallback is not tightly bounded')

forum=read('portal/services/forum_sources.py')
if 'Native forum search is a fallback after browsing marketplace/listing pages' not in forum:
    fail('forum query planner missing broad fallback explanation')
block=forum.split('def build_forum_queries',1)[1].split('def default_forum_listing_paths',1)[0]
if ' OR ' in block or '(' in re.sub(r'\([^)]*\)', '', block):
    fail('forum query planner contains Boolean-style grouping')
if "q=f'{intent} {term}'" in block:
    fail('forum fallback still glues intent to rare tech term')

discovery=read('portal/services/discovery.py')
if '"paid help" OR "paid project"' in discovery or 'careers OR jobs OR hiring' in discovery:
    fail('discovery still has OR-heavy search query strings')
for token in ["for phrase in ('paid help','paid project','contractor')", "safe_role=' '.join(re.sub", "company_intents=['careers','jobs','hiring'", "q=(f'site:{domain} \"{safe_role}\" {intent}'"]:
    if token not in discovery:
        fail(f'discovery missing split-query token: {token}')

migration=ROOT/'portal'/'migrations'/'0104_v01073_forum_query_stall.py'
if not migration.is_file(): fail('0.10.73 stale forum release migration missing')
if 'bounded forum-query repair' not in migration.read_text(encoding='utf-8'):
    fail('0.10.73 stale forum migration message missing')

# The SQL helper can use SQL OR; generated web/search query builders must not.
query_files=['portal/services/fresh_sources.py','portal/services/forum_sources.py','portal/services/discovery.py','portal/services/search.py']
for rel in query_files:
    text=read(rel)
    forbidden=['(hiring OR','job OR remote','careers OR jobs','"paid help" OR']
    for bad in forbidden:
        if bad in text:
            fail(f'{rel} still contains query contaminant {bad!r}')

print('ScoutBox 0.10.73 targeted regressions passed.')
