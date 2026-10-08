#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.4 searchable dropdown filtering."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
css = (root / 'portal/static/portal/app.css').read_text(encoding='utf-8')
base = (root / 'templates/portal/base.html').read_text(encoding='utf-8')

assert '.searchable-select-option[hidden]' in css, 'searchable select hidden override missing'
assert '.country-option[hidden]' in css, 'country picker hidden override missing'
assert '[data-multi-select-option-search][hidden]' in css, 'multi-select hidden override missing'
assert 'display:none!important' in css, 'hidden option override must win over flex display rules'
assert 'function initSearchableSelects' in base and 'function filter()' in base, 'searchable select initializer missing'
assert 'b.hidden=!!q' in base, 'searchable select filter no longer uses hidden state'
print('ScoutBox 0.11.4 searchable dropdown static regression checks passed.')
