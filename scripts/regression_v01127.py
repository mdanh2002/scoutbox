#!/usr/bin/env python3
"""ScoutBox 0.11.27 regression: leased Hidden Lead reassessment resume and Add buttons."""
import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
tasks=(root/'portal'/'tasks.py').read_text()
views=(root/'portal'/'views.py').read_text()
campaigns=(root/'templates'/'portal'/'campaigns.html').read_text()
contacts=(root/'templates'/'portal'/'contacts.html').read_text()
css=(root/'portal'/'static'/'portal'/'app.css').read_text()
assert "HIDDEN_LEAD_REASSESSMENT_RELEASE = '0.11.27'" in tasks
assert 'HIDDEN_LEAD_REASSESSMENT_QUEUE_RECOVERY_SECONDS = 90' in tasks
assert 'HIDDEN_LEAD_REASSESSMENT_LEASE_SECONDS' in tasks
assert 'def _claim_hidden_lead_reassessment_execution' in tasks
assert 'def _dispatch_hidden_lead_reassessment_job' in tasks
assert 'def _update_hidden_lead_reassessment_job' in tasks
assert "hidden_lead_minibrowser_reassessment_job(self, job_id, execution_token='')" in tasks
assert "hidden_lead_minibrowser_reassessment_job.delay(job_id,token)" in tasks
assert "current_app.control.revoke(task_id,terminate=True,signal='SIGTERM')" in tasks
assert "return _dispatch_hidden_lead_reassessment_job(existing,settings_row,reason='unowned_worker_recovery')" in tasks
assert "pass_state['processed']=max(int(pass_state.get('processed') or 0),len(completed))" in tasks
assert "if token and current_token != token:" in tasks
assert "current_item" in tasks and "clear_current=True" in tasks
assert "from portal.tasks import _dispatch_hidden_lead_reassessment_job" in views
assert "reason='skip_current'" in views
assert "'release':'0.11.27'" in views
assert "{% icon 'campaign_add' %}" not in campaigns
assert "{% icon 'template_add' %}" not in campaigns
assert campaigns.count('<span class="toolbar-plus">+</span>') >= 2
assert contacts.count('<span class="toolbar-plus">+</span>') >= 1
assert '.list-toolbar .toolbar-icon-add' in css
assert 'background:#177a45!important' in css
for py in [root/'portal'/'tasks.py', root/'portal'/'views.py']:
    ast.parse(py.read_text(), filename=str(py))
print('0.11.27 regression checks passed')
