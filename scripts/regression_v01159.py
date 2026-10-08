#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.59 configured-campaign Daily Digest."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.59'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.59'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.59'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.59'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.59.md').exists()

digest=read('portal/services/digest.py')
assert 'Campaign,' in digest
assert 'CampaignRun,' not in digest
assert "Campaign.objects.filter(deleted_at__isnull=True).order_by('name')" in digest
assert "'created':_fmt_date(campaign.created_at)" in digest
assert '<h2>Configured campaigns</h2>' in digest
assert "lines.extend(['','CONFIGURED CAMPAIGNS'])" in digest
assert 'Created {row["created"]}' in digest
assert "('Configured campaigns',f'{configured_campaign_count:,}')" in digest
for stale in (
    'Campaigns · last 24 hours',
    'CAMPAIGNS · LAST 24 HOURS',
    'No campaign runs in the last 24 hours.',
    'campaign_runs_24h',
    'run_kind',
):
    assert stale not in digest, stale

notes=read('docs/RELEASE_NOTES_0.11.59.md')
assert 'configured Campaign list' in notes
assert 'creation date' in notes
print('ScoutBox 0.11.59 regression checks passed')
