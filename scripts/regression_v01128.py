#!/usr/bin/env python3
"""ScoutBox 0.11.28 regression: DB-complete re-evaluation history popups."""
import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
views=(root/'portal'/'views.py').read_text()
opportunities=(root/'templates'/'portal'/'opportunities.html').read_text()
contacts=(root/'templates'/'portal'/'contacts.html').read_text()
hidden=(root/'templates'/'portal'/'cold_contact.html').read_text()
assert 'def _manual_filter_history_for_view' in views
assert 'The history popup is intentionally DB-complete' in views
assert '_manual_filter_lightweight_history' not in views
assert "BackgroundJob.objects.filter(kind=kind).order_by('-created_at','-pk')" in views
assert "opportunity_filter_history=_manual_filter_history_for_view('filter_opportunities',active_opportunity_filter)" in views
assert "contact_filter_history=_manual_filter_history_for_view('filter_contacts',active_contact_filter)" in views
assert 'hidden_lead_filter_history=_hidden_lead_filter_history_for_view(active_hidden_lead_filter)' in views
assert '_hidden_lead_filter_history_for_view(active_hidden_lead_filter,10)' not in views
assert "candidates=list(BackgroundJob.objects.filter(kind='filter_hidden_leads').order_by('-created_at')[:40])" not in views
for template, token in [
    (opportunities, 'All {{opportunity_filter_history|length}} stored run'),
    (contacts, 'All {{contact_filter_history|length}} stored run'),
    (hidden, 'All {{hidden_lead_filter_history|length}} stored run'),
]:
    assert token in template
    assert 'Last {{' not in template
for py in [root/'portal'/'views.py']:
    ast.parse(py.read_text(), filename=str(py))
print('0.11.28 regression checks passed')
