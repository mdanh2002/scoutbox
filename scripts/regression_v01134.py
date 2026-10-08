#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.34 list multiselect Apply behavior and history details."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / 'portal/static/portal/app.css').read_text()
base = (ROOT / 'templates/portal/base.html').read_text()
contacts = (ROOT / 'templates/portal/contacts.html').read_text()
opportunities = (ROOT / 'templates/portal/opportunities.html').read_text()
hidden = (ROOT / 'templates/portal/cold_contact.html').read_text()
search_log = (ROOT / 'templates/portal/search_log.html').read_text()
combined = contacts + opportunities + hidden + search_log

checks = [
    ("0.11.34 CSS block present", "ScoutBox 0.11.34 — deferred Apply controls" in css),
    ("Address Book rows forced compact", "#contacts-bulk .list-toolbar details.multi-select-filter .list-multi-select-panel label.multi-select-option-row" in css and "height:30px!important" in css and "max-height:30px!important" in css),
    ("Address Book checkboxes reset", "#contacts-bulk .list-toolbar details.multi-select-filter .list-multi-select-panel input[type=\"checkbox\"]" in css and "max-height:16px!important" in css and "padding:0!important" in css),
    ("Address Book icon-free grid remains compact", "details.multi-select-filter.no-option-icons" in css and "grid-template-columns:16px minmax(0,1fr)!important" in css),
    ("List filters have search boxes", "Search locations" in contacts and "Search focuses" in contacts and "Search campaigns" in opportunities and "Search campaigns" in hidden),
    ("Apply button added to every multiselect", combined.count('multi-select-apply-btn') >= 10),
    ("Provider filters use Apply", search_log.count('multi-select-apply-btn') == 2 and 'applyMultiSelectFilter(this)' in search_log),
    ("List filter checkboxes no longer directly navigate", 'markListMultiFilterCustom(this);applyListMultiFilter(this)' not in combined),
    ("Deferred Apply JS present", "function applyMultiSelectFilter" in base and "snapshotMultiSelectFilter" in base and "restoreMultiSelectFilter" in base),
    ("Async change ignores multiselect checkbox edits", "closest?.('details.multi-select-filter')" in base and "return;if(event.target&&event.target.matches('[data-async-filter]')" in base),
    ("Async request URL normalizes multiselect params", "form.querySelectorAll('details.multi-select-filter').forEach" in base and "url.searchParams.delete(name)" in base),
    ("Single-result re-evaluation class rendered", "manual-filter-single-row-table" in contacts and "manual-filter-single-row-table" in opportunities and "manual-filter-single-row-table" in hidden),
    ("Single-result re-evaluation CSS present", "compact single-entry re-evaluation details" in css and "td:nth-child(6)::before" in css),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('0.11.34 regression failed: ' + ', '.join(failed))
print('0.11.34 regression checks passed')
