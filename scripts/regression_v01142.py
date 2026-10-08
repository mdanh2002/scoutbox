from pathlib import Path

root=Path(__file__).resolve().parents[1]
views=(root/'portal/views.py').read_text(encoding='utf-8')
urls=(root/'portal/urls.py').read_text(encoding='utf-8')
stats=(root/'templates/portal/stats.html').read_text(encoding='utf-8')
css=(root/'portal/static/portal/app.css').read_text(encoding='utf-8')
svg=(root/'portal/static/portal/world-map.svg').read_text(encoding='utf-8')

assert 'stats_map_resolve_async' in views, 'progressive Statistics map resolver view missing'
assert "stats/map/resolve/" in urls and "name='stats_map_resolve'" in urls, 'progressive map resolver URL missing'
assert "_STATS_MAP_CACHE_KEY='stats_map_geo_v2'" in views, 'map coordinate cache key missing'
assert 'Do not infer map coordinates from TLDs' in views, 'blacklist TLD-location guard missing'
assert "return ['Worldwide']" not in views[views.index('def _stats_blacklist_locations'):views.index('def _stats_add_record_point')], 'blacklist should not default to worldwide marker'
assert "location in _STATS_MAP_BROAD_LABELS" in views and "location in _STATS_MAP_LARGE_COUNTRY_CENTROIDS" in views, 'broad/large country centroid suppression missing'
assert "fetch('{% url \"stats_map_resolve\" %}?'+query()" in stats, 'client-side progressive resolver fetch missing'
assert 'markerKey(layerKey,point)' in stats and 'data-point-key' in stats, 'map point de-duplication missing'
assert 'drawExportLegend(ctx,exportZoom' in stats and "strokeText(rowInfo.label" in stats, 'export legend must render readable high-resolution labels'
assert 'drawPin(ctx,x*exportZoom,y*exportZoom,layerColor(layer.key),52)' in stats, 'export pins should render as fixed, readable high-resolution map pins'
assert '.stats-map-export button:hover' in css and '.stats-map-zoom button:hover' in css, 'map control hover styles missing'
for label in ['Antarctica','Greenland','Southern Ocean','Moscow','Novosibirsk','Vladivostok','San Francisco','Seattle']:
    assert label in svg, f'map label missing: {label}'
print('ScoutBox 0.11.42 regression checks passed')
