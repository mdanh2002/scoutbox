#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.43 Global Activity Map polish."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
stats = (ROOT / 'templates/portal/stats.html').read_text(encoding='utf-8')
css = (ROOT / 'portal/static/portal/app.css').read_text(encoding='utf-8')
svg = (ROOT / 'portal/static/portal/world-map.svg').read_text(encoding='utf-8')
assert (ROOT / 'VERSION').read_text().strip() in {'0.11.43','0.11.44'}, 'VERSION is not 0.11.43+'
assert (ROOT / 'docs/RELEASE_NOTES_0.11.43.md').exists(), 'release notes missing'
assert 'ScoutBox 0.11.43' in css, '0.11.43 CSS override missing'
assert 'transform:none!important' in css, 'map controls must not shift on hover/focus'
assert 'drawExportLegend(ctx,exportZoom,activeLayers)' in stats, 'export legend function missing'
legend = stats[stats.index('function drawExportLegend'):stats.index('async function exportMapPng')]
assert 'Global Activity Map' not in legend, 'export legend should not draw heading'
assert 'roundedRect' not in legend, 'export legend should not draw a bordered/background box'
assert 'strokeText(rowInfo.label' in legend and 'fillText(rowInfo.label' in legend, 'export legend should draw readable label rows'
assert 'drawPin(ctx,pad+7*z' in legend, 'export legend should draw pin swatches'
draw_pin = stats[stats.index('function drawPin'):stats.index('function roundedRect')]
assert 'ctx.rotate' not in draw_pin, 'canvas export pin should not use broken rotated arc shape'
assert 'bezierCurveTo' in draw_pin, 'canvas export pin should use a stable teardrop path'
assert 'drawPin(ctx,x*exportZoom,y*exportZoom,layerColor(layer.key),52)' in stats, 'exported map pins should use fixed readable size'
for label in ['Ottawa','Edmonton','Anchorage','Phoenix','Kansas City','Dakar','Kinshasa','Addis Ababa','Nizhny Novgorod','Omsk','Krasnoyarsk','Yakutsk','Khabarovsk','Tehran','Riyadh','Dhaka','Chengdu','Perth','McMurdo Station']:
    assert label in svg, f'map label missing: {label}'
print('0.11.43 regression checks passed')
