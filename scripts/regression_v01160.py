#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.60 Setup Overview alignment."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.60'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.60'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.60'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.60'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.60.md').exists()

dash=read('templates/portal/dashboard.html')
assert 'readiness-selectivity-detail' in dash
assert 'dashboard-selectivity-links readiness-selectivity-links' in dash
for label in ('Jobs: ','Leads: ','Contacts: '):
    assert label in dash

css=read('portal/static/portal/app.css')
assert '#first-run-readiness .readiness-selectivity-detail{justify-content:flex-start}' in css
assert '#first-run-readiness .readiness-selectivity-links{justify-content:flex-start}' in css
notes=read('docs/RELEASE_NOTES_0.11.60.md')
assert 'same detail-column edge' in notes
print('ScoutBox 0.11.60 regression checks passed')
