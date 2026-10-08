from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
opp = (ROOT / 'templates/portal/opportunity_detail.html').read_text()
lead = (ROOT / 'templates/portal/hidden_lead_detail.html').read_text()
contacts = (ROOT / 'templates/portal/contacts.html').read_text()

assert '<div class="stat-kpi"><span>Job location</span>' not in opp
assert '<div class="stat-kpi country-kpi"><span>Job country</span>' not in opp
assert '<b>Source URL</b>' in opp
assert '<b>Job location</b><span class="readonly-location-line"' in opp
assert '<b>Job country</b><span class="readonly-location-line"' in opp
assert opp.index('<b>Campaign</b>') < opp.index('<b>Source URL</b>') < opp.index('<b>Job location</b>') < opp.index('<b>Job country</b>')

assert '<div class="stat-kpi"><span>Company location</span>' not in lead
assert '<div class="form-row"><label>Company location</label>{% with location_text=lead|record_locations_display' not in lead
assert '<b>Company location</b><span class="readonly-location-line"' in lead
assert lead.index('<b>Campaign</b>') < lead.index('<b>Source URL</b>') < lead.index('<b>Company location</b>')

assert 'id="contact-company-country-readonly"' in contacts
assert contacts.index('id="contact-source"') < contacts.index('id="contact-company-country-readonly"') < contacts.index('<button class="btn primary">Save</button>')

print('0.11.6 detail location layout regression passed')
