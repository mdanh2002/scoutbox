from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tasks = (ROOT / 'portal' / 'tasks.py').read_text()
migration = (ROOT / 'portal' / 'migrations' / '0144_v0119_hidden_lead_reassessment.py').read_text()

required = [
    'def hidden_lead_minibrowser_reassessment_job',
    'deletions_deferred_until_completed',
    'protected_outreach_not_recycled',
    'pending_recycle.append',
    'Only now, after every active Hidden Lead has been assessed',
    'def _hidden_lead_has_outreach',
    'draft_subject',
    'draft_body',
    '_queue_hidden_lead_minibrowser_reassessment',
]
for needle in required:
    assert needle in tasks, f'missing task guard: {needle}'
assert 'v0119_hidden_lead_minibrowser_reassessment_pending' in migration
assert "0143_v0115_source_readonly_location_repair" in migration
assert 'fetch_pages=True' not in migration
assert 'hidden_lead_minibrowser_admission' not in migration
print('0.11.9 regression checks passed')
