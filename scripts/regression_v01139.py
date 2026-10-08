#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.39 stats and dropdown hotfixes."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
css=(ROOT/'portal/static/portal/app.css').read_text()
views=(ROOT/'portal/views.py').read_text()
checks=[
    ('version bumped', (ROOT/'VERSION').read_text().strip()=='0.11.39'),
    ('stats map payload guarded', "logger.exception('Statistics map payload failed')" in views and "stats_map_payload={'viewBox': {'width':1440,'height':720}, 'layers': []}" in views),
    ('applications map query not deferred badly', "applications.select_related('opportunity')[:800]" in views and "applications.select_related('opportunity').only('pk','opportunity__" not in views),
    ('01139 css block present', 'ScoutBox 0.11.39' in css),
    ('dropdown parent overflow visible', '.card:has(details.multi-select-filter[open])' in css and 'overflow:visible!important' in css),
    ('recycle dropdown high z', '.recycle-filter-form details.recycle-type-filter .list-multi-select-panel' in css and 'z-index:6000!important' in css),
    ('applications select height parity', '.applications-toolbar .app-filter' in css and 'height:34px!important' in css),
]
failed=[name for name,ok in checks if not ok]
if failed:
    raise SystemExit('0.11.39 regression failed: '+', '.join(failed))
print('0.11.39 regression checks passed')
