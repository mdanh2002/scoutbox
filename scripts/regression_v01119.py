from pathlib import Path

root = Path(__file__).resolve().parents[1]
tasks = (root / 'portal' / 'tasks.py').read_text()
views = (root / 'portal' / 'views.py').read_text()
extras = (root / 'portal' / 'templatetags' / 'portal_extras.py').read_text()
cold = (root / 'templates' / 'portal' / 'cold_contact.html').read_text()

assert "HIDDEN_LEAD_REASSESSMENT_RELEASE = '0.11.19'" in tasks
assert 'def _hidden_lead_existing_reassessment_item' in tasks
assert 'resume from' in tasks.lower() or 'resumable' in tasks.lower()
assert "stats['processed'] = 0" in tasks or "'processed': 0" in tasks
assert 'manual_filter_meaningful_items' in extras
assert "placeholder" in extras
assert "detail_items=run.result|manual_filter_meaningful_items" in cold
assert "completed_hidden_lead_filter_history=[job for job in completed_hidden_lead_filter_history if _latest_meaningful_manual_filter([job])]" in views
assert '0147_v01119_resumable_hidden_lead_reassessment' in ''.join(p.name for p in (root/'portal'/'migrations').glob('0147*.py'))
print('ScoutBox 0.11.19 regression checks passed')
