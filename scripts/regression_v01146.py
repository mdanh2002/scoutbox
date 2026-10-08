#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.46 map polish and Email History footer alignment."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
stats = (ROOT / 'templates/portal/stats.html').read_text(encoding='utf-8')
css = (ROOT / 'portal/static/portal/app.css').read_text(encoding='utf-8')
svg = (ROOT / 'portal/static/portal/world-map.svg').read_text(encoding='utf-8')
email = (ROOT / 'templates/portal/email_history.html').read_text(encoding='utf-8')
assert (ROOT / 'VERSION').read_text().strip() == '0.11.46', 'VERSION is not 0.11.46'
assert (ROOT / 'RELEASE_ID').read_text().strip() == 'ScoutBox 0.11.46', 'RELEASE_ID stale'
assert 'id="stats-map-export-png"' not in stats, 'Export PNG button should be hidden/removed from map UI'
last = css[css.rfind('ScoutBox 0.11.46'):]
assert '.stats-map-export{display:none!important;}' in last, 'map export CSS hide override missing'
assert '.city-layer circle{display:none}' in svg, 'confusing city dots should be hidden'
assert '.city-layer text' in svg and 'font-size:6.3px' in svg, 'major city labels should remain readable'
assert '.city-layer .supplemental-city text{font-size:5.45px' in svg, 'supplemental city labels should remain visible'
assert '.city-layer .dense-city text{font-size:4.55px' in svg, 'dense city labels should remain present but lighter'
assert 'transform:translateY(2px)!important;' in last, 'Email History count vertical nudge missing'
assert 'font-weight:400!important;' in last, 'Email History count should not be bold'
assert 'margin-right:12px!important;' in last, 'Email History count right margin missing'
assert email.count('email-history-count') == 3, 'Email History count should remain in all three footers'
print('ScoutBox 0.11.46 regression checks passed')
