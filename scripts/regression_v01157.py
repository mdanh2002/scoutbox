#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.57 discovery guidance/dashboard placement."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.57'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.57'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.57'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.57'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.57.md').exists()

settings=read('templates/portal/settings.html')
hint='Defines how ScoutBox decides which discovered entries are relevant enough to keep.'
assert hint in settings
assert settings.count(hint)==1

dash=read('templates/portal/dashboard.html')
assert '<h3>Setup Overview</h3>' in dash
assert 'First Run Readiness' not in dash
assert 'readiness-selectivity-row' in dash
assert 'discovery-preferences-icon' in dash
assert "{% icon 'info' %}" in dash
for label,anchor in (
    ('Jobs: ','settings-general-opportunity-selectivity'),
    ('Leads: ','settings-general-lead-selectivity'),
    ('Contacts: ','settings-general-contact-selectivity'),
):
    assert label in dash and anchor in dash
# Selectivity links no longer occupy the Background Work header.
activity= dash[dash.index('<div class="card span-12 activity-pulse-card"'):dash.index('<div class="metric-strip span-12">')]
assert 'dashboard-selectivity-links' not in activity
assert 'dashboard-search-control' in activity
# They are present in the Setup Overview row instead.
setup=dash[dash.index('<div class="card span-12" id="first-run-readiness"'):dash.index('<div class="card span-12 dashboard-recent-campaigns">')]
assert 'dashboard-selectivity-links readiness-selectivity-links' in setup
assert 'Discovery preferences' in setup

css=read('portal/static/portal/app.css')
assert '#settings-general .settings-subsection-hint' in css
assert '#first-run-readiness .readiness-selectivity-detail' in css
assert '#first-run-readiness .discovery-preferences-icon' in css

notes=read('docs/RELEASE_NOTES_0.11.57.md')
assert 'Discovery & Relevance guidance' in notes
assert 'No discovery, selectivity, campaign, contact-admission, or dashboard behavior changed' in notes

print('ScoutBox 0.11.57 regression checks passed')
