from pathlib import Path

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.107'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.107'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.107'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.107'
assert (root / 'docs/RELEASE_NOTES_0.11.107.md').exists()

rules = read('templates/portal/link_rules.html')
links = read('templates/portal/links.html')
css = read('portal/static/portal/app.css')

# Requested copy/UI changes.
assert '>Import links</label>' in rules
assert '>Scan DOCX</span>' in rules
assert 'placeholder="dsmp3"' not in rules
assert 'tracking-docx-file-input sr-only' in rules
assert 'tracking-docx-filename' in rules
assert '.tracking-file-field{width:100%!important;overflow:hidden!important;border:0!important;' in css

# Closing either by X or modal backdrop refreshes the parent Tracking Links view.
assert 'function closeTrackingAddModal(){closeModal(\'tracking-add-modal\');window.location.reload()}' in links
assert 'onclick="if(event.target===this)closeTrackingAddModal()"' in links
assert 'onclick="closeTrackingAddModal()" aria-label="Close"' in links

# Preserve dynamic sizing and configured Blog-base generation behavior.
assert "frame.style.setProperty('height',height+'px','important')" in links
assert "'ResizeObserver'in window" in rules
tracking = read('portal/services/tracking.py')
assert "public_base=blog_base_url().rstrip('/')" in tracking
assert "full=public_base+'/'+stem_path.lstrip('/')" in tracking

mig = read('portal/migrations/0179_v011107_tracking_dialog_polish.py')
assert "version='0.11.107'" in mig
assert '0178_v011106_tracking_blog_base_generation' in mig
print('ScoutBox 0.11.107 targeted regression checks passed')
