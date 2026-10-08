#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.51 summary/list-view fixes."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
read = lambda rel: (ROOT / rel).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.51', 'VERSION is not 0.11.51'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.51', 'RELEASE_ID stale'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.51', 'BUILD_INFO stale'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.51', 'README stale'

cold = read('portal/services/cold.py')
tasks = read('portal/tasks.py')
views = read('portal/views.py')
tags = read('portal/templatetags/portal_extras.py')
css = read('portal/static/portal/app.css')
base = read('templates/portal/base.html')
campaigns = read('templates/portal/campaigns.html')

# Hidden Leads summary specificity: generic taxonomy text is detected rather than emitted.
for token in (
    'def hidden_lead_summary_is_generic(summary):',
    "'emulation and virtualization technology'",
    'def _specific_company_summary_candidate(summary, company=',
    'Retained verified company facts:',
    'return exactly SUMMARY_PENDING',
    'company_intel=None',
):
    assert token in cold, f'Hidden Leads summary guard missing: {token}'

prelim = cold[cold.index('def preliminary_company_summary('):cold.index('\ndef is_general_market_host', cold.index('def preliminary_company_summary('))]
assert 'company_summary_from_intel(company_intel or {},1200)' in prelim, 'preliminary summary does not prefer retained company facts'
assert '_evidence_summary_fallback' in prelim, 'preliminary summary lost evidence fallback'
assert "return ''" in prelim, 'preliminary summary must permit a pending/no-claim state'
assert "Specializes in {context}" not in prelim, 'generic taxonomy fallback was reintroduced'

# Regression for the stale undefined deadline block that prevented summary/draft execution.
short = cold[cold.index('def short_company_summary('):cold.index('\ndef preliminary_company_summary', cold.index('def short_company_summary('))]
assert '_remaining(' not in short and 'review =' not in short and 'cutoff =' not in short, 'stale MiniBrowser deadline code remains in short_company_summary'
draft = cold[cold.index('def generate_cold_draft('):]
first_draft_chunk = draft[:1800]
assert '_remaining(' not in first_draft_chunk, 'stale MiniBrowser deadline code remains at generate_cold_draft entry'

# Existing duplicate/generic summaries are repairable without list-page cloud fan-out.
assert 'summary_counts=Counter(' in views, 'list-level duplicate summary detection missing'
assert 'market_summary_needs_refresh(x.summary)' in views, 'generic summary refresh gate missing'
assert 'summary_counts.get(' in views, 'exact duplicate refresh gate missing'
assert "or 'Summary pending.'" in views, 'safe pending fallback missing from existing-record repair'
assert 'company_intel=lead.company_intel' in views, 'repair path is not using retained company facts'

# Background refinements carry company facts through and research can replace generic summaries.
assert 'short_company_summary(lead.company,page_title,evidence,lead.company_intel)' in tasks, 'summary job does not pass company intel'
assert 'market_summary_needs_refresh(lead.summary)' in tasks, 'company research does not repair stale summaries'
assert 'company_summary_from_intel(lead.company_intel or {},1200)' in tasks, 'company research does not use retained facts'

# List display refuses known boilerplate rather than swapping in a keyword list.
assert 'def hidden_lead_list_summary(lead):' in tags
assert 'hidden_lead_summary_is_generic(stored)' in tags
assert "return 'Summary pending.'" in tags
assert 'company_summary_from_intel' in tags

# Show/Hide Deleted is a shared neutral toolbar action until explicitly active.
marker = '/* ScoutBox 0.11.51 — Hidden Leads/list toolbar and Campaign Template consistency. */'
assert marker in css, '0.11.51 CSS block missing'
block = css[css.index(marker):]
for token in (
    '.toolbar-action-cluster .show-deleted-toggle:not(.active)',
    '.toolbar-actions-right .show-deleted-toggle:not(.active)',
    'border-color:#37657f!important;',
    '.show-deleted-toggle:not(.active):focus-visible',
):
    assert token in block, f'Show/Hide Deleted shared style missing: {token}'

# Focus text must leave the caret unobscured, particularly for one long selected focus.
focus_rule = re.search(r'\.multi-select-filter\.focus-filter>summary>\.select-label\{([^}]*)\}', block, re.S)
assert focus_rule, 'Focus label/caret spacing rule missing'
assert 'min-width:0!important;' in focus_rule.group(1)
assert 'text-overflow:ellipsis!important;' in focus_rule.group(1)
assert 'margin-right:8px!important;' in focus_rule.group(1)

# Native icon-select mouse focus should not remain highlighted after outside dismissal.
assert 'function initToolbarSelectFocusRelease()' in base, 'toolbar select focus-release initializer missing'
assert "document.addEventListener('pointerdown'" in base, 'outside pointer focus release missing'
assert "active instanceof HTMLSelectElement&&active.closest('.toolbar-select-button')" in base, 'toolbar select guard missing'
assert 'active.blur()' in base, 'toolbar select blur action missing'
assert 'initToolbarSelectFocusRelease();' in base, 'toolbar select focus-release initializer not invoked'

# Campaign Templates: toolbar before/outside card; table and footer inside bordered card.
section = campaigns[campaigns.index('<section id="campaign-templates"'):campaigns.index('<div class="modal" id="template-editor"')]
idx_toolbar = section.index('standalone-template-toolbar')
idx_card = section.index('campaign-template-list-card')
idx_table = section.index('id="template-table"')
idx_footer = section.index('class="list-footer-two"')
assert idx_toolbar < idx_card < idx_table < idx_footer, 'Campaign Templates toolbar/list shell ordering is wrong'
card_tail = section[idx_card:]
assert 'id="template-table"' in card_tail and 'class="list-footer-two"' in card_tail, 'Campaign Templates card does not contain table/footer'
assert '.campaign-template-list-form>.standalone-template-toolbar' in block, 'Campaign Templates standalone toolbar style missing'

print('ScoutBox 0.11.51 regression checks passed')
