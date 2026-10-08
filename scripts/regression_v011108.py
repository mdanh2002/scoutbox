from pathlib import Path

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.108'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.108'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.108'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.108'
assert (root / 'docs/RELEASE_NOTES_0.11.108.md').exists()

rules = read('templates/portal/link_rules.html')
links = read('templates/portal/links.html')
css = read('portal/static/portal/app.css')
icons = read('portal/templatetags/portal_extras.py')

# Approved 0.11.108 Tracking Link wording/alignment.
assert '>Generate</button>' in rules
assert 'Test &amp; Generate</button>' not in rules
assert '<th>Link</th><th>Page title</th><th data-nosort>Action</th>' in rules
assert "Click Generate to resolve and generate it." in rules
assert "btn.textContent=label||'Generate'" in rules
assert "trackingTestButton('Generate',false)" in rules
assert "grid-template-columns:var(--tracking-label) minmax(0,1fr)!important" in css
assert '#tracking-test-result.result-grid .kv>b' in css

# File uploader outline restored without reverting the custom filename control.
assert 'tracking-docx-file-input sr-only' in rules
assert 'tracking-docx-filename' in rules
assert '.tracking-file-field{border:1px solid #31516a!important;' in css

# Scanned DOCX action uses a semantic load icon with no surrounding button border.
assert 'tracking-scan-action-btn' in rules
assert "{% icon 'tracking_load' %}" in rules
assert 'title="Use this link"' in rules
assert "'tracking_load':" in icons
assert '#tracking-docx-table .tracking-scan-action-btn{border:0!important;' in css

# Preserve prior behavior.
assert '>Import links</label>' in rules
assert '>Scan DOCX</span>' in rules
assert 'placeholder="dsmp3"' not in rules
assert 'function closeTrackingAddModal(){closeModal(\'tracking-add-modal\');window.location.reload()}' in links
assert "frame.style.setProperty('height',height+'px','important')" in links
assert "'ResizeObserver'in window" in rules
tracking = read('portal/services/tracking.py')
assert "public_base=blog_base_url().rstrip('/')" in tracking
assert "full=public_base+'/'+stem_path.lstrip('/')" in tracking

mig = read('portal/migrations/0180_v011108_tracking_link_ui_alignment.py')
assert "version='0.11.108'" in mig
assert '0179_v011107_tracking_dialog_polish' in mig
print('ScoutBox 0.11.108 targeted regression checks passed')
