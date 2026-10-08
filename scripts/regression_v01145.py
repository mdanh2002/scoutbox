#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.45 map/export and Email History polish."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
stats = (ROOT / 'templates/portal/stats.html').read_text(encoding='utf-8')
css = (ROOT / 'portal/static/portal/app.css').read_text(encoding='utf-8')
svg = (ROOT / 'portal/static/portal/world-map.svg').read_text(encoding='utf-8')
email = (ROOT / 'templates/portal/email_history.html').read_text(encoding='utf-8')
assert (ROOT / 'VERSION').read_text().strip() in {'0.11.45','0.11.46'}, 'VERSION is not 0.11.45+'
assert (ROOT / 'RELEASE_ID').read_text().strip() in {'ScoutBox 0.11.45','ScoutBox 0.11.46'}, 'RELEASE_ID stale'
assert 'stats-map-marker-multi' in stats and 'count>1' in stats, 'multi-point markers not classified'
assert '.stats-map-marker-multi' in css and '23px!important' in css, 'multi-point marker 130% sizing missing'
assert 'function svgExportImage' in stats and 'fetch(mapImg.currentSrc||mapImg.src' in stats, 'high-res SVG export loader missing'
assert "(count>1?23:18)*exportZoom" in stats, 'exported pins are not scaled with export zoom'
assert 'ctx.arc(0,cy,r' in stats and 'ctx.lineTo(0,0)' in stats, 'export pin path is not the stable location-pin shape'
assert ('.city-layer .dense-city text{font-size:4.3px' in svg or '.city-layer .dense-city text{font-size:4.55px' in svg), 'dense city label sizing missing'
assert '.country-label{fill:#56646a;font-size:8.6px' in svg, 'country label density sizing missing'
for text in ['Dallas','Austin','Houston','New Orleans','Prague','Budapest','Kuala Lumpur']:
    assert text in svg, f'expected map label missing: {text}'
assert 'email-history-count' in email, 'Email History count missing'
last = css[css.rfind('ScoutBox 0.11.45'):]
assert 'font-weight:400!important' in last, 'Email History count should not be bold'
assert 'margin-right:10px!important' in last, 'Email History count right margin missing'
assert ('line-height:28px!important' in last or 'line-height:30px!important' in last), 'Email History footer vertical alignment missing'
print('ScoutBox 0.11.45 regression checks passed')
