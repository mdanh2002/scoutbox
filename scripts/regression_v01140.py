from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
stats = (ROOT / 'templates/portal/stats.html').read_text(encoding='utf-8')
css = (ROOT / 'portal/static/portal/app.css').read_text(encoding='utf-8')
views = (ROOT / 'portal/views.py').read_text(encoding='utf-8')
svg = (ROOT / 'portal/static/portal/world-map.svg').read_text(encoding='utf-8')
checks = [
    ('map has drag viewport binding', 'viewport.addEventListener(\'pointerdown\'' in stats and 'is-dragging' in stats),
    ('map tooltips use payload tooltip', 'point.tooltip' in stats and 'btn.dataset.tooltip' in stats),
    ('map scrollbars hidden', 'scrollbar-width:none' in css and 'stats-map-viewport::-webkit-scrollbar' in css),
    ('layer controls top left', 'left:18px!important' in css and 'right:auto!important' in css),
    ('map heading divider removed', '.stats-world-map-card>h3{border-bottom:0!important;}' in css),
    ('blacklist plotted as individual records', 'for row in blacklisted.only' in views and '_stats_blacklist_locations' in views and 'Domain/URL' in views),
    ('application/contact wording retained', 'Applications/Outreach' in views and "_stats_geo_layer('contacts','Contact'" in views),
    ('svg has expanded labels', 'Johannesburg' in svg and 'South Africa' in svg and 'Arctic Ocean' in svg and 'Nigeria' in svg and 'Saudi Arabia' in svg),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('FAILED: ' + '; '.join(failed))
print('0.11.40 regressions passed')
