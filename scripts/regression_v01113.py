#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
extras=(root/'portal/templatetags/portal_extras.py').read_text()
css=(root/'portal/static/portal/app.css').read_text()
opp=(root/'templates/portal/opportunities.html').read_text()
lead=(root/'templates/portal/cold_contact.html').read_text()
contacts=(root/'templates/portal/contacts.html').read_text()
assert '_looks_urlish_display' in extras and '_role_from_urlish' in extras, 'missing URL display guards'
assert 'if _looks_urlish_display(raw_title)' in extras, 'opportunity title raw URL guard missing'
assert 'return brand if brand' in extras, 'company URL brand fallback missing'
for icon in ['read_all','read_unread','read_seen','mark_state']:
    assert f"'{icon}'" in extras, f'missing {icon} icon'
assert 'ScoutBox 0.11.13' in css and 'icon-only read-state' in css, '0.11.13 CSS block missing'
assert 'min-width:36px' in css and 'width:36px' in css, 'icon controls should be compact'
for template in (opp,lead,contacts):
    assert "{% icon 'mark_state' %}" in template, 'mark control should be icon-only'
    assert "{% icon 'read_all' %}" in template, 'read-state all icon missing'
    assert 'toolbar-select-button-label">Mark' not in template, 'text Mark label still visible'
assert 'Unread{% elif read_state' not in opp, 'opportunity visible text read labels remain'
print('0.11.13 URL display and icon toolbar regression passed')
