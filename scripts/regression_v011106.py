from pathlib import Path
from urllib.parse import urlparse

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.106'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.106'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.106'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.106'
assert (root / 'docs/RELEASE_NOTES_0.11.106.md').exists()

tracking = read('portal/services/tracking.py')

# Allocation must retain the configured Blog base path instead of rebuilding from host root.
assert "public_base=blog_base_url().rstrip('/')" in tracking
assert "full=public_base+'/'+stem_path.lstrip('/')" in tracking
assert "path=urlparse(full).path or '/'" in tracking
assert "parsed=urlparse(blog_base_url()); root=f'{parsed.scheme}://{parsed.netloc}'" not in tracking
assert "full=urljoin(root,path)" not in tracking

# Example from the reported regression.
public_base='https://toughdev.com/blog'.rstrip('/')
stem_path='/fatfs'+'integrating'
full=public_base+'/'+stem_path.lstrip('/')
assert full == 'https://toughdev.com/blog/fatfsintegrating'
assert urlparse(full).path == '/blog/fatfsintegrating'

# Preserve the .105 dynamic scan-height fix and .103 layout behavior.
css = read('portal/static/portal/app.css')
rules = read('templates/portal/link_rules.html')
links = read('templates/portal/links.html')
assert '.tracking-add-frame{height:170px;min-height:0!important}' in css
assert "frame.style.setProperty('height',height+'px','important')" in links
assert "'ResizeObserver'in window" in rules
assert '>Short URL</label>' in rules
assert 'tracking-docx-file-input sr-only' in rules and 'tracking-docx-filename' in rules

mig = read('portal/migrations/0178_v011106_tracking_blog_base_generation.py')
assert "version='0.11.106'" in mig
assert '0177_v011105_tracking_dialog_scan_height' in mig
print('ScoutBox 0.11.106 targeted regression checks passed')
