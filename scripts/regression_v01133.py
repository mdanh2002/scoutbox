#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.33 Hidden Lead history detail cleanup."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cold = (ROOT / 'templates/portal/cold_contact.html').read_text()

checks = [
    ("hidden summary remains point form", 'manual-filter-history-summary-block' in cold and 'manual-filter-history-points' in cold),
    ("hidden summary starts with active-run guard", "{% if run.status == 'running' or run.status == 'queued' %}{% with processed=run.result|manual_filter_count:'processed'" in cold),
    ("hidden summary closes before table", '{% endwith %}{% endif %}\n              {% with detail_items=run.result|manual_filter_meaningful_items %}' in cold),
    ("past/manual details still render table", 'manual-filter-history-table' in cold and 'manual_filter_meaningful_items' in cold),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('0.11.33 regression failed: ' + ', '.join(failed))
print('0.11.33 regression checks passed')
