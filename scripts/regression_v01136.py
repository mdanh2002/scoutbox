#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.36 searchable filters and offline Statistics map."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
views = (ROOT / 'portal/views.py').read_text()
base = (ROOT / 'templates/portal/base.html').read_text()
css = (ROOT / 'portal/static/portal/app.css').read_text()
search_log = (ROOT / 'templates/portal/search_log.html').read_text()
gpt_log = (ROOT / 'templates/portal/gpt_log.html').read_text()
audit = (ROOT / 'templates/portal/audit.html').read_text()
blacklist = (ROOT / 'templates/portal/blacklist.html').read_text()
recycle = (ROOT / 'templates/portal/recycle_bin.html').read_text()
stats = (ROOT / 'templates/portal/stats.html').read_text()
world_svg = ROOT / 'portal/static/portal/world-map.svg'
world_geo = ROOT / 'portal/services/world_geo.py'

checks = [
    ("0.11.36 CSS block present", "ScoutBox 0.11.36" in css),
    ("Search Activity outcomes are searchable Apply multiselect", "outcome-filter no-option-icons" in search_log and "Search outcomes" in search_log and "status_mode" in search_log and "applyMultiSelectFilter(this)" in search_log),
    ("Search Activity view supports outcome multi-values", "outcome_state=_selected_filter_values(request,'status'" in views and "selected_outcome_label" in views and "status_values" in views),
    ("AI runtime/provider/status filters are searchable", all(x in gpt_log for x in ("gpt-runtime-filter no-option-icons", "Search runtimes", "gpt-provider-filter no-option-icons", "Search providers", "gpt-status-filter no-option-icons", "Search statuses"))),
    ("AI view supports runtime/provider/status multi-values", all(x in views for x in ("runtime_state=_selected_filter_values(request,'runtime'", "provider_state=_selected_filter_values(request,'provider'", "status_state=_selected_filter_values(request,'status'", "_apply_runtime_filter", "_apply_provider_filter", "_apply_status_filter"))),
    ("AI footer preserves multi filters", all(x in gpt_log for x in ("runtime_mode", "provider_mode", "task_mode", "status_mode", "runtime_values", "provider_values", "status_values"))),
    ("Audit action filter is searchable", "audit-action-filter no-option-icons" in audit and "Search actions" in audit and "action_mode" in audit),
    ("Audit view supports action multi-values", "action_state=_selected_filter_values(request,'action')" in views and "_apply_values_filter(base,'action'" in views),
    ("Blacklist scope filter is searchable", "blacklist-scope-filter no-option-icons" in blacklist and "Search scopes" in blacklist and "scope_mode" in blacklist),
    ("Blacklist view supports scope multi-values", "scope_state=_selected_filter_values(request,'scope'" in views and "scope_filter_label" in views and "scope_options" in views),
    ("Recycle Bin type filter is searchable", "recycle-type-filter no-option-icons" in recycle and "Search types" in recycle and "item_type_mode" in recycle),
    ("Recycle Bin view supports type multi-values", "item_type_state=_selected_filter_values(request,'item_type'" in views and "item_type_filter_label" in views and "item_type_options" in views),
    ("Deferred Apply/revert JS remains present", all(x in base for x in ("function applyMultiSelectFilter", "restoreMultiSelectFilter", "function filterMultiSelectPanel", "submitAsyncFilterForm"))),
    ("Offline world map asset present", world_svg.exists() and world_svg.stat().st_size > 50000 and '<svg' in world_svg.read_text(errors='ignore')[:100]),
    ("World map coordinates service present", world_geo.exists() and "def location_point" in world_geo.read_text() and "COUNTRY_POINTS" in world_geo.read_text()),
    ("Statistics template renders offline map", all(x in stats for x in ("stats-world-map-card", "portal/world-map.svg", "stats-map-layer-controls", "stats-map-zoom", "stats-world-map-data", "initStatsWorldMap"))),
    ("Statistics view supplies map payload", "_statistics_world_map_payload" in views and "stats_map_json=stats_map_payload" in views),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('0.11.36 regression failed: ' + ', '.join(failed))
print('0.11.36 regression checks passed')
