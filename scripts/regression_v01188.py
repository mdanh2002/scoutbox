from pathlib import Path

root = Path(__file__).resolve().parents[1]
read = lambda name: (root / name).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.88'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.88'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.88'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.88'
assert (root / 'docs/RELEASE_NOTES_0.11.88.md').exists()

facebook = read('templates/portal/facebook_pages.html')
assert "await portalConfirm('Move the selected Facebook Pages" in facebook
assert "restoreInlineItem('facebook_page'" in facebook
assert "confirm('Move the selected Facebook Pages" not in facebook

links = read('templates/portal/links.html')
assert '<th data-sortable>Article</th><th data-sortable>Application</th>' in links
assert '|compact_external_url' in links
assert 'confirmRecycleDelete' in links

rules = read('templates/portal/link_rules.html')
assert 'tracking-docx-table' in rules
assert 'scoutbox-tracking-frame-height' in rules
assert '<h3>Tracking Link Configuration</h3>' not in rules

telemetry = read('templates/portal/telemetry.html')
assert "segment.total)+' entries ('+segment.ring+')'" in telemetry
assert 'function resourceDisplayRange(data){const dates=' in telemetry
assert 'metric-info-button' not in telemetry

about = read('templates/portal/about.html')
for heading in ('Common data checks', 'Useful scripts &amp; key files', 'Terminal &amp; SQL examples', 'Redis usage', 'External Statistics'):
    assert heading in about

css = read('portal/static/portal/app.css')
assert '.facebook-pages-main-toolbar{gap:5px!important}' in css
assert '.tracking-add-modal-card{width:min(980px,94vw)!important;height:auto!important' in css

migration = read('portal/migrations/0160_v01188_ui_workflow_repairs.py')
assert "version='0.11.88'" in migration
print('ScoutBox 0.11.88 regression checks passed')
