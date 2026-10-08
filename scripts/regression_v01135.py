#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.35 searchable Applications/AI filters."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
views = (ROOT / 'portal/views.py').read_text()
base = (ROOT / 'templates/portal/base.html').read_text()
css = (ROOT / 'portal/static/portal/app.css').read_text()
applications = (ROOT / 'templates/portal/applications.html').read_text()
gpt_log = (ROOT / 'templates/portal/gpt_log.html').read_text()
search_log = (ROOT / 'templates/portal/search_log.html').read_text()

checks = [
    ("0.11.35 CSS block present", "ScoutBox 0.11.35 — searchable Apply-first filters" in css),
    ("Applications location is searchable multiselect", "applications-location-filter" in applications and "Search locations" in applications and "country_mode" in applications and "applyMultiSelectFilter(this)" in applications),
    ("Applications location no longer immediate select", "applications-country-filter" not in applications and "navigateListFacet('country'" not in applications),
    ("Applications view parses multiselect state", "country_state=_request_multi_filter_state(request,'country',canonicalizer=_canonical_country_name)" in views and "_apply_country_filters(qs,'opportunity__country',country_filter_values,country_state['mode'])" in views),
    ("Applications status/channel preserve multiple locations", "getAll('country').forEach" in applications and "country_mode" in applications),
    ("AI task type is searchable multiselect", "gpt-task-filter no-option-icons" in gpt_log and "Search task types" in gpt_log and "task_mode" in gpt_log and "applyMultiSelectFilter(this)" in gpt_log),
    ("AI task view supports multiple values", "task_state=_request_multi_filter_state(request,'task')" in views and "stage__in=task_type_values" in views and "task_filter_label=_multi_filter_label('task types'" in views),
    ("AI task sort links preserve repeated task params", "gpt_log_sort_query=urlencode(filter_pairs,doseq=True)" in views and gpt_log.count("{{gpt_log_sort_query}}&sort=") == 7),
    ("Search Activity provider type has search", "Search provider types" in search_log and "data-multi-select-option-search=\"{{t.label}} {{t.value}}\"" in search_log),
    ("Deferred Apply/revert JS remains present", "function applyMultiSelectFilter" in base and "restoreMultiSelectFilter" in base and "event.target?.closest?.('details.multi-select-filter')" in base),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('0.11.35 regression failed: ' + ', '.join(failed))
print('0.11.35 regression checks passed')
