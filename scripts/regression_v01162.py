#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.62 location/map/list-toolbar cleanup."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.62'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.62'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.62'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.62'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.62.md').exists()

stats=read('templates/portal/stats.html')
assert 'id="stats-updated"' not in stats
assert 'Last updated {{stats_updated' not in stats
assert 'Statistics live refresh skipped' in stats
assert 'Records at this location:' in stats
assert 'function nearbyPoint' in stats
assert 'addedPins' in stats

views=read('portal/views.py')
assert "_STATS_MAP_CACHE_KEY='stats_map_geo_v4'" in views
assert 'def _stats_map_evidence_fingerprint' in views
assert "payload['evidence_fingerprint']=fingerprint" in views
assert 'def _stats_aggregate_map_points' in views
assert "mapped_count=sum(max(1,int(x.get('count') or 1)) for x in displayed)" in views
assert 'def _stats_record_map_locations' in views

locations=read('portal/services/location_values.py')
assert 'def _record_explicit_region_items' in locations
assert "return 'structured_jobposting' in sources" in locations
assert 'Small explicit' in locations
jobloc=read('portal/services/location.py')
assert 'REGION_DEFS' in jobloc
assert 'Fast path for broad recruiter regions' in jobloc
assert 'Remote\\s+from' in jobloc

css=read('portal/static/portal/app.css')
assert '.standalone-list-toolbar{position:sticky;top:55px;' in css
assert '.sticky-range-card{position:sticky;top:55px;' in css
assert '.troubleshooting-command-grid .terminal-command:last-child{border-bottom:0}' in css

telemetry=read('templates/portal/telemetry.html')
assert 'Usage Events' in telemetry or 'usage' in telemetry.lower()  # intentionally retained
notes=read('docs/RELEASE_NOTES_0.11.62.md')
for phrase in ('Source-native recruiter regions','stats_map_geo_v4','Usage Events','US-heavy'):
    assert phrase in notes
print('ScoutBox 0.11.62 regression checks passed')
