#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.49 Statistics Global Activity Map."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
views = (ROOT / 'portal/views.py').read_text(encoding='utf-8')
stats = (ROOT / 'templates/portal/stats.html').read_text(encoding='utf-8')
css = (ROOT / 'portal/static/portal/app.css').read_text(encoding='utf-8')

assert (ROOT / 'VERSION').read_text().strip() == '0.11.49', 'VERSION is not 0.11.49'
assert (ROOT / 'RELEASE_ID').read_text().strip() == 'ScoutBox 0.11.49', 'RELEASE_ID stale'
assert (ROOT / 'BUILD_INFO.txt').read_text().strip() == 'ScoutBox v0.11.49', 'BUILD_INFO stale'

# Map legend shows only records actually represented by rendered markers.
assert "const mapped=Number(layer.mapped_count==null?0:layer.mapped_count)" in stats, 'mapped-only legend count missing'
assert "+' ('+mapped.toLocaleString()+')'" in stats, 'mapped-only legend label missing'
assert "Number(layer.mapped_count||0)" in stats, 'PNG export legend must use mapped count'
assert ' mapped / ' not in stats, 'old mapped/total wording still present'
assert "displayed=visible[:800]" in views, 'mapped count must be based on displayed point slice'
assert "mapped_count=sum(int(x.get('count') or 1) for x in displayed)" in views, 'displayed mapped count missing'

# User-facing missing-location hint and spacing.
assert 'stats-map-location-hint' in stats, 'map location hint missing'
assert 'Some items may be hidden due to insufficient location data.' in stats, 'map location hint copy missing'
assert '.stats-world-map-card{' in css and 'margin-bottom:24px!important;' in css, 'map bottom spacing missing'
assert '.stats-world-map-card>h3 .stats-map-location-hint' in css, 'map hint styling missing'
assert 'text-align:right!important;' in css, 'map hint must be right aligned'

# Invalidate prior permissive map caches and make new resolution provenance-safe.
assert "_STATS_MAP_CACHE_KEY='stats_map_geo_v3'" in views, 'map cache namespace was not bumped'
assert "stats_map_geo_v2" not in views, 'old map cache key still active'
assert "if out.get('precise') is True:\n        return out" in views, 'precise map points must not be jittered away from their coordinates'
assert 'def _stats_location_label_supported' in views, 'AI location provenance validation missing'
assert 'Use only the supplied LOCATION EVIDENCE.' in views, 'AI resolver location-only instruction missing'
assert 'AI location was not explicitly supported by location evidence' in views, 'AI location evidence rejection missing'
assert "direct=_stats_direct_location_point(item['details'], *item['labels'])" in views, 'resolver still scans non-location URL/text'
assert "raw_values=(details,)" in views, 'candidate pre-check still scans non-location fields'

# Main layer rendering must feed only location-bearing fields to direct coordinate resolution.
for token in (
    "raw_values=(row.role_location,row.locations,row.country)",
    "raw_values=(row.locations,row.country)",
    "raw_values=(row.company_locations,row.company_country)",
    "raw_values=(opp.role_location,opp.locations,opp.country)",
):
    assert token in views, f'location-only map input missing: {token}'

candidate_section = views[views.index('def _stats_map_candidate_details'):views.index('def _stats_map_enqueue_candidate')]
for forbidden in ('row.description','row.raw_search_snippet','row.summary','row.match_summary','row.evidence','row.company_summary'):
    assert forbidden not in candidate_section, f'general content leaked into location resolver: {forbidden}'

# Blacklist rows have no native location field: only matched records with retained location evidence may place them.
blacklist_section = views[views.index('def _stats_blacklist_locations'):views.index('def _stats_add_record_point')]
assert 'Do not infer map coordinates from TLDs, company names, reasons, or broad defaults.' in blacklist_section, 'blacklist no-guess guard missing'
assert 'return []' in blacklist_section, 'blacklist text should not be treated as a location field'
assert '_stats_direct_location_point(row.label,row.reason)' not in views, 'blacklist company/reason text still creates map coordinates'
assert "add(row,location_labels,(row.role_location,row.locations,row.country),'Opportunity')" in views, 'blacklist Opportunity evidence is not location-only'
assert "add(row,location_labels,(row.locations,row.country),'Hidden Lead')" in views, 'blacklist Hidden Lead evidence is not location-only'
assert "add(row,location_labels,(row.company_locations,row.company_country),'Address Book')" in views, 'blacklist Address Book evidence is not location-only'
assert "company_specific_blacklist_review_domain_for_record(record)" in views, 'safe company-domain evidence matching missing'
assert "_BLACKLIST_TLD_LOCATIONS" not in blacklist_section[blacklist_section.index('def _stats_blacklist_locations'):], 'TLD table must not be used by blacklist resolver'

print('ScoutBox 0.11.49 regression checks passed')
