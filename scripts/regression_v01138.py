#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.38 map and Email History UI updates."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
stats = (ROOT / 'templates/portal/stats.html').read_text()
css = (ROOT / 'portal/static/portal/app.css').read_text()
views = (ROOT / 'portal/views.py').read_text()
base = (ROOT / 'templates/portal/base.html').read_text()
email = (ROOT / 'templates/portal/email_history.html').read_text()
svg = (ROOT / 'portal/static/portal/world-map.svg').read_text()
checks = [
    ("version bumped", (ROOT / 'VERSION').read_text().strip() == '0.11.38'),
    ("map heading improved", '<h3>Global Activity Map</h3>' in stats and '<h3>World Map</h3>' not in stats),
    ("map layer controls have no glyph icon", 'stats-map-layer-icon' not in stats and "label.append(cb,text)" in stats),
    ("map pins use ScoutBox floating tooltip", "scout-multiline-tooltip" in stats and "btn.dataset.tooltip" in stats),
    ("map pins navigate to URLs", "window.location.href=url" in stats and "point.url" in stats),
    ("map payload has new labels", "'Contact'" in views and "'Applications/Outreach'" in views and "'Address Book'" not in views[views.index('def _statistics_world_map_payload'):views.index('def _apply_focus_filters')]),
    ("map payload links records", "reverse('opportunity_detail'" in views and "reverse('hidden_lead_detail'" in views and "reverse('application_edit'" in views and "reverse('contacts')" in views),
    ("map marker shape is pin not circle glyph", "border-radius:50% 50% 50% 0!important" in css and "color:transparent!important" in css and "stats-map-marker-blacklist{background:#df4b48" in css),
    ("legend chrome removed", ".stats-map-layer-controls{" in css and "border:0!important" in css and "background:transparent!important" in css),
    ("zoom margin increased", "right:26px!important" in css and "bottom:26px!important" in css),
    ("light SVG map styling exists", "#e7f5fb" in svg and ".country{fill:#f4efe4" in svg and "Pacific Ocean" in svg and "United States" in svg and "Europe" in svg),
    ("email footer targets exist", "data-pager-count=\"incoming-mail\"" in email and "data-pager-page=\"incoming-mail\"" in email and "data-pager-nav=\"incoming-mail\"" in email),
    ("email top toolbar no row controls", "email-history-top-toolbar" in email and "data-pager-count=\"outgoing-mail\"" in email and "data-pager-count=\"draft-mail\"" in email),
    ("base pager supports split count/page", "data-pager-count" in base and "data-pager-page" in base and "countText=found.length" in base and "pageText='page '+page+' / '+pages" in base),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('0.11.38 regression failed: ' + ', '.join(failed))
print('0.11.38 regression checks passed')
