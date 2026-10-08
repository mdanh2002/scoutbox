from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / 'portal/static/portal/app.css').read_text()
cold = (ROOT / 'templates/portal/cold_contact.html').read_text()
views = (ROOT / 'portal/views.py').read_text()
extras = (ROOT / 'portal/templatetags/portal_extras.py').read_text()
assert 'hidden-lead-skip-current-action' in cold and 'skipCurrentHiddenLeadReassessment' in cold
assert "'/jobs/'+encodeURIComponent(jobId)+'/skip-current/'" in cold
assert 'def _prune_zero_roundtrip_country_options' in views
assert "country_options=_prune_zero_roundtrip_country_options" in views
assert "return '◇'" in extras and "return '🗺️'" not in extras
assert '.mark-state-action-button::after' in css and 'display:none!important' in css
assert 'read-state-filter-button.read-state-all::before' in css
print('regression_v01115 ok')
