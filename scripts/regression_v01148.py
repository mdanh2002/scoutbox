#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.48 Statistics blacklist map recovery."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
views = (ROOT / 'portal/views.py').read_text(encoding='utf-8')
stats = (ROOT / 'templates/portal/stats.html').read_text(encoding='utf-8')

assert (ROOT / 'VERSION').read_text().strip() == '0.11.48', 'VERSION is not 0.11.48'
assert (ROOT / 'RELEASE_ID').read_text().strip() == 'ScoutBox 0.11.48', 'RELEASE_ID stale'
assert (ROOT / 'BUILD_INFO.txt').read_text().strip() == 'ScoutBox v0.11.48', 'BUILD_INFO stale'

for token in (
    'def _stats_blacklist_evidence_index',
    'def _stats_structured_coordinate_point',
    "source='structured_location'",
    'normalize_company_blacklist_key',
    'company_specific_blacklist_review_domain_for_record',
    "'source':'Opportunity'".replace("'source':'Opportunity'", "'source':source_label"),
    "_stats_blacklist_evidence(row,blacklist_evidence)",
    "_stats_jittered_point(evidence['point'],f\"blacklist:{row.pk}\")",
    "'Location unavailable'",
    "'mapped_count':mapped_count",
):
    assert token in views, f'missing blacklist map recovery token: {token}'

blacklist_section = views[views.index('def _stats_blacklist_locations'):views.index('def _stats_add_record_point')]
assert 'Do not infer map coordinates from TLDs' in blacklist_section, 'TLD location guard removed'
assert "return ['Worldwide']" not in blacklist_section, 'blacklist must not default to Worldwide'
assert "_BLACKLIST_TLD_LOCATIONS" not in blacklist_section[blacklist_section.index('def _stats_blacklist_locations'):], 'TLD map table must not be used by blacklist resolver'
assert "company_specific_blacklist_review_domain_for_record(record)" in views, 'safe company-domain evidence matching missing'
assert "layer.key==='blacklist'&&mapped<total" in stats, 'Blacklist mapped/total legend missing'
assert "mapped.toLocaleString()+' mapped / '+total.toLocaleString()" in stats, 'Blacklist mapped count wording missing'
print('ScoutBox 0.11.48 regression checks passed')
