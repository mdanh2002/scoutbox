from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
stats = (ROOT / 'templates/portal/stats.html').read_text(encoding='utf-8')
email = (ROOT / 'templates/portal/email_history.html').read_text(encoding='utf-8')
css = (ROOT / 'portal/static/portal/app.css').read_text(encoding='utf-8')
views = (ROOT / 'portal/views.py').read_text(encoding='utf-8')
notes = (ROOT / 'docs/RELEASE_NOTES_0.11.44.md').read_text(encoding='utf-8')

assert 'id="stats-map-zoom-value"' in stats, 'zoom percentage span missing'
assert "zoomValue=document.getElementById('stats-map-zoom-value')" in stats, 'zoom percentage element not wired'
assert "if(zoomValue)zoomValue.textContent=zoom+'%'" in stats, 'zoom percentage not updated on zoom change'

last_css = css[css.find('ScoutBox 0.11.44'):]
assert '.stats-map-export{right:28px!important;}' in last_css, 'export control right edge is not normalized'
assert 'right:28px!important;' in last_css and 'width:142px!important;' in last_css, 'zoom control alignment/width missing'
assert 'text-decoration:none!important;' in last_css, 'legend underline override missing'
assert 'transform:none!important;' in last_css, 'stable no-shift hover override missing'
assert 'display:flex!important;' in last_css and '#stats-map-zoom-value' in last_css, 'readable zoom value CSS missing'

assert 'Click to open' not in views, 'map tooltip still contains click-to-open text'
assert "_stats_map_line('URL'" not in views, 'map tooltip still contains URL lines'
assert "_stats_map_line('Domain/URL'" not in views, 'map tooltip still contains Domain/URL lines'

assert 'email-history-range-card' not in email, 'separate Email History range card still present'
assert email.count('email-history-inline-range') == 3, 'date range toolbar should be inline in all three Email History tab toolbars'
for table, template_count in [('incoming-mail','{{incoming|length}} items'),('outgoing-mail','{{outgoing|length}} items'),('draft-mail','{{other|length}} items')]:
    assert f'data-pager-count="{table}"' in email, f'{table} item count missing'
    footer_idx = email.find(f'data-pager-count="{table}"')
    page_idx = email.find(f'data-pager-page="{table}"')
    nav_idx = email.find(f'data-pager-nav="{table}"')
    assert footer_idx != -1 and page_idx != -1 and nav_idx != -1 and footer_idx < page_idx < nav_idx, f'{table} footer order should be count, page, nav'
assert '.email-history-inline-range' in last_css, 'Email History inline range CSS missing'

assert 'readable zoom percentage' in notes.lower(), 'release notes do not mention zoom percentage fix'
assert 'Email History' in notes, 'release notes do not mention Email History layout fix'
print('ScoutBox 0.11.44 regression checks passed')
