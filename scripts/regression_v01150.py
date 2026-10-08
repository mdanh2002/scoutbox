#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.50 searchable-filter stacking."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / 'portal/static/portal/app.css').read_text(encoding='utf-8')
contacts = (ROOT / 'templates/portal/contacts.html').read_text(encoding='utf-8')
base = (ROOT / 'templates/portal/base.html').read_text(encoding='utf-8')

assert (ROOT / 'VERSION').read_text().strip() == '0.11.50', 'VERSION is not 0.11.50'
assert (ROOT / 'RELEASE_ID').read_text().strip() == 'ScoutBox 0.11.50', 'RELEASE_ID stale'
assert (ROOT / 'BUILD_INFO.txt').read_text().strip() == 'ScoutBox v0.11.50', 'BUILD_INFO stale'

# Reproduce the reported Address Book controls: Search + location/focus checkbox filters.
assert 'data-table-filter="contacts-table"' in contacts, 'Address Book Search control missing'
assert 'class="multi-select-filter country-filter location-filter has-option-icons"' in contacts, 'Address Book location multiselect missing'
assert 'class="multi-select-filter focus-filter no-option-icons"' in contacts, 'Address Book focus multiselect missing'

# Shared dropdown implementations used across list views.
assert "wrap.className='searchable-select-wrap'" in base, 'shared searchable select wrapper missing'
assert "wrap.className='country-combobox'" in base, 'shared country combobox wrapper missing'
assert "wrap.classList.add('open')" in base and "wrap.classList.remove('open')" in base, 'searchable select open-state class missing'

# 0.11.50 stacking contract: closed custom controls have no promoted z-index.
marker = '/* ScoutBox 0.11.50 — custom searchable filter stacking contract.'
assert marker in css, '0.11.50 stacking override missing'
block = css[css.index(marker):]
for token in (
    '.main details.multi-select-filter,',
    '.main #contacts-bulk details.multi-select-filter{',
    'z-index:auto!important;',
    '.main details.multi-select-filter[open],',
    '.main #contacts-bulk details.multi-select-filter[open]{',
    '.main .searchable-select-wrap.open{',
    '.main .country-combobox:focus-within{',
    'z-index:18!important;',
):
    assert token in block, f'stacking rule missing: {token}'

# The global header remains above active list dropdowns (20 > 18).
assert '.topbar{' in css and 'z-index:20' in css, 'global topbar stacking baseline changed unexpectedly'

# Open checkbox panels must still be absolute overlays, not layout-expanding content.
assert '.multi-select-filter-panel{position:absolute;' in css, 'multiselect panel overlay behavior missing'
assert '.searchable-select-panel{position:absolute;' in css, 'searchable select panel overlay behavior missing'
assert '.country-options-popover{position:absolute;' in css, 'country popover overlay behavior missing'

print('ScoutBox 0.11.50 regression checks passed')
