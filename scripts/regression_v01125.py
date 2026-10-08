#!/usr/bin/env python3
"""ScoutBox 0.11.25 regression: Hidden Lead reassessment resumes durably."""
import ast
from pathlib import Path
root = Path(__file__).resolve().parents[1]
tasks = (root / 'portal' / 'tasks.py').read_text()
views = (root / 'portal' / 'views.py').read_text()
migration = (root / 'portal' / 'migrations' / '0148_v01125_durable_hidden_lead_reassessment.py').read_text()
assert "HIDDEN_LEAD_REASSESSMENT_PASS_KEY" in tasks
assert "hidden_lead_minibrowser_reassessment_pass" in tasks
assert "resume_from_per_lead_state" in tasks
assert "Exact-label matching caused new versions to" in tasks
assert "revived_after_stale_running" in tasks
assert "existing_hidden_lead_minibrowser_reassessment_skipped_current" in views
assert "Replaced by durable-pass Hidden Lead reassessment resume" in migration
assert "status == 'completed'" in migration
for py in [root / 'portal' / 'tasks.py', root / 'portal' / 'views.py', root / 'portal' / 'migrations' / '0148_v01125_durable_hidden_lead_reassessment.py']:
    ast.parse(py.read_text(), filename=str(py))
print('0.11.25 regression checks passed')
