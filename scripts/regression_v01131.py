#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.31 dropdown/history UI repair."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text()

def require(condition, message):
    if not condition:
        raise SystemExit(message)

css = read('portal/static/portal/app.css')
require('ScoutBox 0.11.31 — final parity for list multiselect dropdowns' in css, 'final 0.11.31 multiselect CSS block missing')
final_block = css.split('ScoutBox 0.11.31 — final parity for list multiselect dropdowns', 1)[1]
require('> input.multi-select-filter-search[type="search"]' in final_block, 'list multiselect search input override missing')
require('input[type="hidden"]{display:none!important' in final_block.replace('\n',''), 'internal hidden mode input can render in dropdown')
require('grid-template-columns:16px 20px minmax(0,1fr)!important' in final_block, 'option rows are not forced to checkbox/icon/text columns')
require('.multi-select-option-icon' in final_block and '.multi-select-option-text' in final_block, 'option icon/text alignment classes missing')
require('text-overflow:ellipsis!important' in final_block, 'option text overflow guard missing')

for template in ['templates/portal/cold_contact.html','templates/portal/opportunities.html','templates/portal/contacts.html']:
    text = read(template)
    require('class="multi-select-filter-search" type="search"' in text, f'{template} missing multiselect search field')
    require('placeholder="Search locations…"' in text, f'{template} still has country search copy')
    require('class="multi-select-filter-divider"' in text, f'{template} missing divider below select/deselect all')
    require('class="multi-select-toggle-all"' in text, f'{template} missing select/deselect all control')
    require('class="multi-select-option-row"' in text, f'{template} missing one-line option row class')
    require('class="multi-select-option-icon"' in text, f'{template} missing option icon column')
    require('class="multi-select-option-text"' in text and 'class="option-count"' in text, f'{template} missing option name/count formatting')
    require('Search countries' not in text and 'All countries' not in text, f'{template} retained old countries wording')

views = read('portal/views.py')
require(views.count("_multi_filter_label('locations'") >= 3, 'list filter summaries do not use Location wording')
require("_multi_filter_label('countries'" not in views, 'old countries summary label remains')
require("'Location'" in views and "'Country'" not in views[views.find("def opportunities_view"):views.find("def applications_view")], 'Opportunity export/list copy did not switch to Location')

for template in ['templates/portal/cold_contact.html','templates/portal/opportunities.html','templates/portal/contacts.html']:
    text = read(template)
    require('manual-filter-history-run-head' not in text, f'{template} still renders duplicate detail header')
    require('manual_filter_provider' not in ''.join(re.findall(r'<div class="manual-filter-history-detail">(.*?)</div>\s*</div>', text, re.S)), f'{template} detail pane still renders route metadata')
    require('manual_filter_count' in text and 'hidden{% endif %}' in text, f'{template} does not hide zero-value history count chips')

print('0.11.31 dropdown/history regression checks passed')
