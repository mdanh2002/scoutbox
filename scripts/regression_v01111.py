from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tasks = (ROOT / 'portal' / 'tasks.py').read_text()
cold = (ROOT / 'portal' / 'services' / 'cold.py').read_text()
migration = (ROOT / 'portal' / 'migrations' / '0145_v01111_bounded_hidden_lead_reassessment.py').read_text()

required_tasks = [
    "HIDDEN_LEAD_REASSESSMENT_RELEASE = '0.11.11'",
    'HIDDEN_LEAD_REASSESSMENT_PER_LEAD_SECONDS = 75',
    'deadline_seconds=HIDDEN_LEAD_REASSESSMENT_PER_LEAD_SECONDS',
    'page_timeout=HIDDEN_LEAD_REASSESSMENT_PAGE_TIMEOUT',
    "decision = 'review'  # Timed-out rows are never automatically recycled.",
    "applied = 'timeout_review' if timed_out else 'review'",
    "'timed_out': stats['timed_out']",
    'HIDDEN_LEAD_REASSESSMENT_LABEL',
]
for needle in required_tasks:
    assert needle in tasks, f'missing bounded reassessment task guard: {needle}'

required_cold = [
    'deadline_seconds=None',
    'deadline_at=None',
    'page_timeout=6',
    'time.monotonic()+float(deadline_seconds)',
    'fetch_target(clean,timeout=max(2,min(int(page_timeout or 6)',
    'ai_timeout=max(8,min(45,int(_remaining(45)-2)))',
    "'source':'0.11.11_hidden_lead_minibrowser_admission_bounded'",
]
for needle in required_cold:
    assert needle in cold, f'missing bounded minibrowser guard: {needle}'

required_migration = [
    'v01111_hidden_lead_minibrowser_reassessment_pending',
    "'per_lead_seconds': 75",
    "'timeouts_are_review_only': True",
    "'protected_outreach_not_recycled': True",
    "message='Superseded by 0.11.11 bounded Hidden Lead reassessment'",
]
for needle in required_migration:
    assert needle in migration, f'missing migration marker: {needle}'

for forbidden in ['fetch_target(', 'generate(', 'hidden_lead_minibrowser_admission(']:
    assert forbidden not in migration, f'migration must not perform runtime work: {forbidden}'
print('0.11.11 regression checks passed')
