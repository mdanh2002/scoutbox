#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.58 Daily Digest footer cleanup."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.58'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.58'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.58'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.58'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.58.md').exists()

digest=read('portal/services/digest.py')
removed=(
    'Each discovery category shows up to 10 new items from today and 10 earlier items from the last 7 days.',
    'Fit scores are intentionally omitted.',
    'Open ScoutBox for the complete lists and operational diagnostics.',
    'Open ScoutBox for the complete opportunity, lead and contact lists.',
)
for phrase in removed:
    assert phrase not in digest, phrase
assert '<footer>' not in digest
assert 'footer{padding:12px 18px;border-top:' not in digest
# The digest still ends with real content and preserves the new/recent split.
assert 'Recent · last 7 days' in digest
assert "_html_campaigns(campaign_rows)" in digest
assert "</div></div></body></html>'" in digest

notes=read('docs/RELEASE_NOTES_0.11.58.md')
assert 'explanatory footer' in notes
assert 'separator line' in notes
print('ScoutBox 0.11.58 regression checks passed')
