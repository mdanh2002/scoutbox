from pathlib import Path

root = Path(__file__).resolve().parents[1]
css = (root / 'portal/static/portal/app.css').read_text()
opp = (root / 'templates/portal/opportunities.html').read_text()
leads = (root / 'templates/portal/cold_contact.html').read_text()
contacts = (root / 'templates/portal/contacts.html').read_text()
extras = (root / 'portal/templatetags/portal_extras.py').read_text()

assert 'ScoutBox 0.11.18 — icon hitbox and running re-evaluation controls' in css
assert '.toolbar-action-cluster .toolbar-select-button select' in css
assert 'max-width:100%!important' in css
assert 'z-index:4!important' in css
assert 'manual-filter-progress-actions' in leads
assert "{% icon 'stop' %}" in leads
assert "Skip current</button>" not in leads
assert ">Status</button>" not in leads + opp + contacts
assert "{% icon 'status_details' %}" in leads + opp + contacts
assert 'manual_filter_has_meaningful_result' in extras
assert "numeric_keys=('kept','recycled','review','protected','timed_out','failed','errors')" in extras
assert 'Latest Re-evaluation Result' in leads + opp
assert 'manual_filter_has_meaningful_result' in leads + opp
assert "Legacy Run" not in leads + opp + contacts
assert "Model not recorded" not in leads + opp + contacts
print('0.11.18 regression checks passed')
