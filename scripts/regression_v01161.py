#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.61 Daily Digest presentation cleanup."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.61'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.61'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.61'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.61'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.61.md').exists()

digest=read('portal/services/digest.py')
assert 'opportunity_specific_highlight' in digest
assert 'def _opportunity_digest_summary(o):' in digest
assert "'highlight':summary, 'description':''" in digest
assert '<th>Company</th><th>Description</th><th>URLs</th>' in digest
assert 'Why / description' not in digest
assert 'Contact / URLs' not in digest
assert "lines.append('   Description: '+row['highlight'])" in digest
assert "row.get('kind')=='contact'" in digest
assert 'contact-company-inline' in digest
assert "'kind':'contact'" in digest
assert 'retained as company-level lead' in digest.lower()
assert 'def _internal_lead_note(value):' in digest
assert 'def _digest_prose(value, limit=260):' in digest
assert '_EXTRACTION_LABEL_RE' in digest

notes=read('docs/RELEASE_NOTES_0.11.61.md')
for phrase in ('same concise, grounded summary','Name — Company','Retained as company-level lead'):
    assert phrase in notes
print('ScoutBox 0.11.61 regression checks passed')
