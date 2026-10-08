#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.5 source-readonly location fields."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
opp_detail = (root / 'templates/portal/opportunity_detail.html').read_text(encoding='utf-8')
lead_detail = (root / 'templates/portal/hidden_lead_detail.html').read_text(encoding='utf-8')
contacts = (root / 'templates/portal/contacts.html').read_text(encoding='utf-8')
loc = (root / 'portal/services/location.py').read_text(encoding='utf-8')
loc_values = (root / 'portal/services/location_values.py').read_text(encoding='utf-8')
views = (root / 'portal/views.py').read_text(encoding='utf-8')
tasks = (root / 'portal/tasks.py').read_text(encoding='utf-8')

assert 'name="country" class="country-picker country-kpi-select"' not in opp_detail, 'Opportunity detail still has editable Job Country dropdown'
assert 'Source-derived job location; read-only' in opp_detail, 'Opportunity detail missing read-only job country display'
assert 'Company location</label><select name="country"' not in lead_detail, 'Hidden Lead detail still has editable company-location dropdown'
assert 'Source-derived company location; read-only' in lead_detail, 'Hidden Lead detail missing read-only location display'
assert 'name="company_country" id="contact-company-country"' not in contacts, 'Address Book modal still posts editable company_country text'
assert 'contact-company-country-readonly' in contacts, 'Address Book modal missing read-only company location display'
assert 'def _jobicy_snapshot_role_location' in loc and 'Remote\\s+from' in loc, 'Jobicy Remote from parser missing'
assert 'source_visible_region_beats_structured_country_array' in (root / 'portal/migrations/0143_v0115_source_readonly_location_repair.py').read_text(encoding='utf-8'), '0.11.5 migration marker missing'
assert 'Rebuild source-readonly location fields for 0.11.5' in tasks, '0.11.5 repair job label missing'
assert '_looks_like_expanded_structured_country_array' in loc_values, 'structured country-array suppression missing'
assert 'malformed_role' in views and '~malformed_role' in views, 'country filter still matches malformed role_location JSON'
print('ScoutBox 0.11.5 source-readonly location static regression checks passed.')
