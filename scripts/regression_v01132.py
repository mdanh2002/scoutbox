#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = (ROOT / 'templates/portal/base.html').read_text()
css = (ROOT / 'portal/static/portal/app.css').read_text()
views = (ROOT / 'portal/views.py').read_text()
cold = (ROOT / 'templates/portal/cold_contact.html').read_text()
opp = (ROOT / 'templates/portal/opportunities.html').read_text()
contacts = (ROOT / 'templates/portal/contacts.html').read_text()
extras = (ROOT / 'portal/templatetags/portal_extras.py').read_text()

checks = [
    ("search uses important inline hide", "style.setProperty('display','none','important')" in base),
    ("explicit high-specificity hidden option css", "label.multi-select-option-row.is-filter-hidden" in css),
    ("campaign dropdown has no icon spacing", 'campaign-filter no-option-icons' in cold and 'campaign-filter no-option-icons' in opp),
    ("focus dropdown has no icon spacing", 'focus-filter no-option-icons' in cold and 'focus-filter no-option-icons' in opp and 'focus-filter no-option-icons' in contacts),
    ("location dropdown keeps icons", 'country-filter location-filter has-option-icons' in cold and 'country-filter location-filter has-option-icons' in opp and 'country-filter location-filter has-option-icons' in contacts),
    ("campaign/focus empty icon spans removed", '<span class="multi-select-option-icon" aria-hidden="true"></span><span class="multi-select-option-text"' not in (cold + opp + contacts)),
    ("all labels include totals", "return f'All {noun} ({int(total or 0)})'" in views),
    ("opportunity all totals passed", "campaign_state['mode'],campaign_total" in views and "opportunity_focus_total" in views),
    ("hidden current title strips progress", 'reassessment_display_message' in cold and 'manual-filter-history-current-title' in cold),
    ("hidden detail is point form", 'manual-filter-history-points' in cold and '<b>Started on:</b>' in cold and '<b>Need review:</b>' in cold),
    ("live history update strips progress", 'function reassessmentDisplayMessage' in cold and "if(msg)msg.textContent=reassessmentDisplayMessage" in cold),
    ("message strip filter exists", 'def reassessment_display_message' in extras),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('0.11.32 regression failed: ' + ', '.join(failed))
print('0.11.32 regression checks passed')
