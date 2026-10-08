#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.41 Global Activity Map legend/export polish."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
stats = (ROOT / 'templates/portal/stats.html').read_text(encoding='utf-8')
css = (ROOT / 'portal/static/portal/app.css').read_text(encoding='utf-8')
checks = [
    ('version at least 0.11.41', (ROOT / 'VERSION').read_text().strip() in {'0.11.41','0.11.42','0.11.43','0.11.44'}),
    ('release notes present', (ROOT / 'docs/RELEASE_NOTES_0.11.41.md').exists()),
    ('map controls are legend', 'stats-map-layer-controls stats-map-legend' in stats and 'aria-label="Map legend"' in stats),
    ('legend rows include pin swatches', 'stats-map-legend-item' in stats and 'stats-map-legend-pin' in stats and 'label.append(cb,pin,text)' in stats),
    ('legend is vertical top left', 'ScoutBox 0.11.41' in css and 'flex-direction:column!important' in css and 'left:22px!important' in css and 'gap:9px!important' in css),
    ('map has top right export button', 'stats-map-export' in stats and 'stats-map-export-png' in stats and 'Export PNG' in stats),
    ('export renders PNG at maximum zoom', 'function exportMapPng()' in stats and 'const exportZoom=10' in stats and "toDataURL('image/png')" in stats),
    ('export respects visible layers', 'if(!visible[layer.key])return;' in stats and 'layers.filter(layer=>visible[layer.key])' in stats),
    ('drag ignores export control', ".stats-map-export" in stats and "e.target.closest('.stats-map-marker,.stats-map-layer-controls,.stats-map-zoom,.stats-map-export')" in stats),
    ('zoom scale label removed', 'stats-map-zoom-label' not in stats and 'zoomLabel' not in stats),
    ('zoom buttons retained', 'stats-map-zoom-out' in stats and 'stats-map-zoom-in' in stats and 'const zoomStops=[25,50,75,100,125,150,175,200,250,300,400,500,750,1000]' in stats),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('0.11.41 regression failed: ' + ', '.join(failed))
print('0.11.41 regression checks passed')
