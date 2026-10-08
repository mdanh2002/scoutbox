from pathlib import Path

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.109'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.109'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.109'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.109'
assert (root / 'docs/RELEASE_NOTES_0.11.109.md').exists()

rules = read('templates/portal/link_rules.html')
links = read('templates/portal/links.html')
css = read('portal/static/portal/app.css')

# Closing the modal must navigate with a fresh GET rather than reload a possibly POST-backed page.
assert "function closeTrackingAddModal(){closeModal('tracking-add-modal');const url=new URL(window.location.href);window.location.assign(url.pathname+url.search+url.hash)}" in links
assert "window.location.reload()" not in links

# Short URL starts at exactly the same middle-column boundary as the other editor rows.
assert '.tracking-shortpath-field .tracking-article-prefix{margin-left:0!important}' in css

# Scan DOCX matches the bordered file uploader's 36px row height.
assert '.tracking-file-field{border:1px solid #31516a!important;' in css
assert '.tracking-docx-scan-button{height:36px!important;min-height:36px!important;max-height:36px!important}' in css

# Preserve prior 0.11.108 wording and behavior.
assert '>Generate</button>' in rules
assert '<th>Link</th><th>Page title</th><th data-nosort>Action</th>' in rules
assert '>Import links</label>' in rules
assert '>Scan DOCX</span>' in rules
assert 'placeholder="dsmp3"' not in rules
assert "frame.style.setProperty('height',height+'px','important')" in links
assert "'ResizeObserver'in window" in rules

mig = read('portal/migrations/0181_v011109_tracking_close_alignment.py')
assert "version='0.11.109'" in mig
assert '0180_v011108_tracking_link_ui_alignment' in mig
print('ScoutBox 0.11.109 targeted regression checks passed')
