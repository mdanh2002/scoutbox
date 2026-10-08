#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.55 digest and General-settings cleanup."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')
def section(text,start,end=None):
    i=text.index(start)
    if end is None: return text[i:]
    j=text.index(end,i+len(start))
    return text[i:j]

assert read('VERSION').strip()=='0.11.55'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.55'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.55'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.55'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.55.md').exists()

digest=read('portal/services/digest.py')
# Calendar-day + prior seven-day category split.
assert 'today_start=local_now.replace(hour=0,minute=0,second=0,microsecond=0)' in digest
assert 'recent_start=now-timedelta(days=7)' in digest
for model_field in ('first_seen_by_portal','created_at'):
    assert f'{model_field}__gte=recent_start' in digest
assert "'<h3 class=\"digest-subheading\">New today</h3>'" in digest
assert "Recent · last 7 days" in digest
assert '_html_category(\'Opportunities\'' in digest
assert '_html_category(\'Hidden Leads\'' in digest
assert '_html_category(\'Address Book\'' in digest

# Digest rows are less noisy.
assert '<th>Company</th><th>Why / description</th><th>Contact / URLs</th>' in digest
assert 'Company / role or focus' not in digest
row_signals=section(digest,'def _row_signals(', '\n\ndef _text_rows')
assert "row.get('fit')" not in row_signals
assert "signals-list" in digest
assert "for signal in _row_signals(row)" in digest

# Operational sections requested for 0.11.55.
assert 'Candidate profile & engagement preferences' in digest
assert 'Campaigns · last 24 hours' in digest
assert 'Major errors' not in digest and 'MAJOR ERRORS' not in digest
assert 'Budget warnings' not in digest and 'BUDGET WARNINGS' not in digest
assert "('Automatic runs'" not in digest
assert 'cloud_auto_runs_per_campaign_day' not in digest

settings=read('templates/portal/settings.html')
for phrase in (
    'Broad allows credible adjacent technical work.',
    'Controls how much company-specific campaign evidence is required',
    'Verified requires strong person-identity and organization evidence.',
):
    assert phrase not in settings
css=read('portal/static/portal/app.css')
assert '#settings-general .selectivity-row select.general-compact-control{width:110px!important;max-width:110px!important;min-width:110px!important}' in css

notes=read('docs/RELEASE_NOTES_0.11.55.md')
assert 'New today' in notes and 'Recent · last 7 days' in notes
assert 'Candidate profile & engagement preferences' in notes
assert 'Major errors' in notes and 'Budget warnings' in notes

print('ScoutBox 0.11.55 regression checks passed')
