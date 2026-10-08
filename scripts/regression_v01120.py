from pathlib import Path
root = Path(__file__).resolve().parents[1]
views = (root / 'portal' / 'views.py').read_text()
extras = (root / 'portal' / 'templatetags' / 'portal_extras.py').read_text()
assert 'def _manual_filter_run_has_visible_history' in views
assert "kind='filter_hidden_leads'" in views
assert '_manual_filter_run_has_visible_history(job)' in views
assert "[:50]" in views
assert 'manual_filter_has_meaningful_result' in extras
# Empty placeholder runs should not count as meaningful in the template filter.
ns={}
# Lightweight textual guard: review is not among top-level meaningful counters.
body = extras.split('def manual_filter_has_meaningful_result',1)[1].split('@register.filter',1)[0]
assert "'review'" not in body
print('ScoutBox 0.11.20 regression checks passed')
