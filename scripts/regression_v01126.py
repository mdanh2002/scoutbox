#!/usr/bin/env python3
"""ScoutBox 0.11.26 regression: canonical Hidden Lead reassessment state/history."""
import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
tasks=(root/'portal'/'tasks.py').read_text()
views=(root/'portal'/'views.py').read_text()
tpl=(root/'templates'/'portal'/'cold_contact.html').read_text()
migration=(root/'portal'/'migrations'/'0149_v01126_canonical_hidden_lead_reassessment.py').read_text()
assert "HIDDEN_LEAD_REASSESSMENT_RELEASE = '0.11.27'" in tasks
assert 'def _hidden_lead_reassessment_seed_state' in tasks
assert "'completed_ids':" in tasks
assert 'def _dispatch_hidden_lead_reassessment_job' in tasks
assert "automatic_hidden_reassessment=_is_existing_hidden_lead_reassessment_job(job)" in views
assert 'def _canonicalize_hidden_lead_reassessment_job' in views
assert 'def _hidden_lead_filter_history_for_view' in views
assert "if _is_existing_hidden_lead_reassessment_job(job):" in views
assert 'refreshHiddenLeadFilterHistoryLive' in tpl
assert 'data-filter-history-job-id' in tpl
assert 'duplicate Hidden Lead reassessment worker' in migration
for py in [root/'portal'/'tasks.py', root/'portal'/'views.py', root/'portal'/'migrations'/'0149_v01126_canonical_hidden_lead_reassessment.py']:
    ast.parse(py.read_text(), filename=str(py))
print('0.11.26/0.11.27 regression checks passed')
