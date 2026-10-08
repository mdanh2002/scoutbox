#!/usr/bin/env python3
"""ScoutBox 0.11.29 regression: reassessment watchdog/AI yielding, meaningful history, list multiselect filters."""
import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
views=(root/'portal'/'views.py').read_text()
tasks=(root/'portal'/'tasks.py').read_text()
ai=(root/'portal'/'services'/'ai.py').read_text()
base=(root/'templates'/'portal'/'base.html').read_text()
opportunities=(root/'templates'/'portal'/'opportunities.html').read_text()
contacts=(root/'templates'/'portal'/'contacts.html').read_text()
hidden=(root/'templates'/'portal'/'cold_contact.html').read_text()
campaigns=(root/'templates'/'portal'/'campaigns.html').read_text()
css=(root/'portal'/'static'/'portal'/'app.css').read_text()

# Hidden Lead reassessment: current release, low-priority AI lane, no fallback, bounded item outcome.
assert "HIDDEN_LEAD_REASSESSMENT_RELEASE = '0.11.29'" in tasks
assert "HIDDEN_LEAD_REASSESSMENT_LABEL = 'Reassess existing Hidden Leads for 0.11.29'" in tasks
assert "local_ai_low_priority=True" in tasks
assert "maintenance_hidden_lead_reassessment=True" in tasks
assert "disable_ai_fallback=True" in tasks
assert "except LocalAILaneBusy as exc" in tasks
assert "local_ai_deferred" in tasks
assert "applied='timeout_review' if timed_out else 'review'" in tasks
assert "job.progress=max(0,min(100,int(progress)))" in tasks
assert "stats['processed']=int(saved.get('processed') or stats['processed'])" in tasks
assert "Automatic reassessment deferred because Local AI was busy" in tasks

assert "maintenance_low_priority = bool(ctx.get('local_ai_low_priority') or ctx.get('maintenance_hidden_lead_reassessment'))" in ai
assert "SCOUTBOX_LOCAL_MAINTENANCE_AI_WAIT_SECONDS" in ai
assert "raise LocalAILaneBusy('Automatic Hidden Lead reassessment deferred because Local AI capacity is busy')" in ai
assert "disable_fallback" in ai and "ctx.get('maintenance_hidden_lead_reassessment')" in ai
assert "if forum_only or disable_fallback:" in ai

# History dialogs: visible current run plus meaningful/error past runs only.
assert "def _manual_filter_run_has_visible_history" in views
assert "Completed no-op" in views
assert "if not _manual_filter_run_has_visible_history(job):" in views
assert "def _manual_filter_history_label" in views
for token in [
    'opportunity_filter_history_label=opportunity_filter_history_label',
    'contact_filter_history_label=contact_filter_history_label',
    'hidden_lead_filter_history_label=hidden_lead_filter_history_label',
]:
    assert token in views
for template, label in [(opportunities,'{{opportunity_filter_history_label}}'),(contacts,'{{contact_filter_history_label}}'),(hidden,'{{hidden_lead_filter_history_label}}')]:
    assert label in template
    assert 'All {{' not in template
    assert 'Last {{' not in template

# Multi-select filter plumbing and templates.
for token in ['def _request_multi_filter_state', 'def _apply_focus_filters', 'def _apply_country_filters', 'def _apply_campaign_filters', 'def _multi_filter_label']:
    assert token in views
for token in ['campaign_mode', 'country_mode', 'focus_mode']:
    assert token in opportunities
    assert token in hidden
for token in ['country_mode', 'focus_mode']:
    assert token in contacts
assert 'campaign_mode' not in contacts.split('<span class="toolbar-actions-right"')[0]
for template in [opportunities, hidden, contacts]:
    assert 'class="multi-select-filter-search"' in template
    assert 'toggleListMultiFilterChecks(this)' in template
    assert 'markListMultiFilterCustom(this)' in template
for token in ['function markListMultiFilterCustom', 'function toggleListMultiFilterChecks', 'function applyListMultiFilter']:
    assert token in base

# Campaign/template show-deleted buttons match the adjacent toolbar icon sizing.
assert campaigns.count('toolbar-icon-action show-deleted-toggle') >= 2
assert '#campaign-list .show-deleted-toggle' in css
assert '#campaign-templates .show-deleted-toggle' in css
assert '.list-multi-select-panel' in css
assert 'ScoutBox 0.11.29' in css

for py in [root/'portal'/'views.py', root/'portal'/'tasks.py', root/'portal'/'services'/'ai.py']:
    ast.parse(py.read_text(), filename=str(py))
print('0.11.29 carry-forward regression checks passed')


# 0.11.30 hotfix: /cold-contact/ must define the history label passed to render.
views_path = root / 'portal' / 'views.py'
views_text = views_path.read_text()
required = "hidden_lead_filter_history_label=_manual_filter_history_label(hidden_lead_filter_history)"
render_arg = "hidden_lead_filter_history_label=hidden_lead_filter_history_label"
assert required in views_text, 'Hidden Lead history label assignment missing; /cold-contact/ would raise NameError'
assert views_text.index(required) < views_text.index(render_arg), 'Hidden Lead history label must be assigned before render context'

print('0.11.30 hotfix regression checks passed')
