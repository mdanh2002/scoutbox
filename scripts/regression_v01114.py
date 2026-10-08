from pathlib import Path
root = Path(__file__).resolve().parents[1]
css = (root/'portal/static/portal/app.css').read_text()
icons = (root/'portal/templatetags/portal_extras.py').read_text()
assert 'ScoutBox 0.11.14' in css
assert '.read-state-filter-button::after' in css
assert 'display:none!important' in css
assert '.read-state-filter-button.read-state-unread::before' in css
assert '.read-state-filter-button.read-state-read::before' in css
assert "'mark_state'" in icons
assert "'read_unread'" in icons and 'circle cx="18" cy="6"' not in icons
print('0.11.14 regression checks passed')
