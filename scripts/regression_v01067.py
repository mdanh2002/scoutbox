#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT/path).read_text(encoding='utf-8')

def fail(msg):
    raise SystemExit(f'FAIL: {msg}')

if read('VERSION').strip()!='0.10.67':
    fail('VERSION not bumped')
if read('RELEASE_ID').strip()!='ScoutBox v0.10.67':
    fail('RELEASE_ID not bumped')
if read('BUILD_INFO.txt').strip()!='ScoutBox v0.10.67':
    fail('BUILD_INFO not bumped')
if not read('README.md').startswith('# ScoutBox 0.10.67'):
    fail('README not bumped')
if not (ROOT/'docs/RELEASE_NOTES_0.10.67.md').exists():
    fail('release notes missing')

search_log=read('templates/portal/search_log.html')
views=read('portal/views.py')
css=read('portal/static/portal/app.css')
verify=read('verify_release.sh')

if '<summary>{{selected_provider_type_label}}</summary>' not in search_log:
    fail('provider type summary still has hard-coded prefix')
if '<summary>{{selected_provider_label}}</summary>' not in search_log:
    fail('provider summary still has hard-coded prefix')
if 'Provider types: {{selected_provider_type_label}}' in search_log:
    fail('old provider type summary prefix remains')
if 'Providers: {{selected_provider_label}}' in search_log:
    fail('old provider summary prefix remains')

needles=[
    "selected_provider_type_label='All Provider Types'",
    "selected_provider_type_label='None'",
    "selected_provider_type_label=f'Provider Types: {len(provider_types)}/{len(provider_type_order)} selected'",
    "selected_provider_label='All Providers'",
    "selected_provider_label='None'",
    "selected_provider_label=f'Providers: {selected_provider_count}/{max(1,len(provider_options))} selected'",
]
for needle in needles:
    if needle not in views:
        fail(f'missing label logic: {needle}')
for stale in ['selected_provider_type_label=\'All types\'', 'selected_provider_label=\'All providers\'', 'None selected']:
    if stale in views:
        fail(f'stale label logic remains: {stale}')
if 'ScoutBox 0.10.67' not in css:
    fail('CSS patch marker missing')
if 'regression_v01067.py' not in verify:
    fail('verify_release does not run v01067 regression')
print('ScoutBox 0.10.67 targeted regressions passed.')
