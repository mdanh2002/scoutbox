from pathlib import Path

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.105'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.105'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.105'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.105'
assert (root / 'docs/RELEASE_NOTES_0.11.105.md').exists()

css = read('portal/static/portal/app.css')
rules = read('templates/portal/link_rules.html')
links = read('templates/portal/links.html')

# Compact initial fallback remains, but it must not be able to defeat dynamic resizing.
assert '.tracking-add-frame{height:170px;min-height:0!important}' in css
assert '.tracking-add-frame{height:170px!important;min-height:0!important}' not in css
assert "frame.style.setProperty('height',height+'px','important')" in links
assert "const needsScroll=requested>available+2" in links
assert "height=Math.max(minimum,Math.min(available,requested))" in links

# The embedded content proactively reports actual size changes after scan/results render.
assert "'ResizeObserver'in window" in rules
assert 'new ResizeObserver(reportTrackingFrameHeight).observe(editor)' in rules
assert 'new MutationObserver(reportTrackingFrameHeight).observe(editor' in rules
assert "window.parent.postMessage({type:'scoutbox-tracking-frame-height',height}" in rules

# Preserve the compact natural-height fixes from .104 and layout behavior from .103.
assert '.embedded-page .app,.embedded-page .main{min-height:0!important;height:auto!important}' in css
assert '.embedded-page .content{flex:0 0 auto!important}' in css
assert '>Short URL</label>' in rules
assert 'tracking-docx-file-input sr-only' in rules and 'tracking-docx-filename' in rules
assert '.tracking-test-button,.tracking-docx-scan-button{width:100%' in css
assert '.tracking-blog-base-line .tracking-save-base-button{flex:1 1 auto' in css
assert 'tracking-article-input{flex:0 0 112px' in css
assert '.date-range-inline>.icon-btn.active,.resource-date-form>.icon-btn.active' in css
assert '.dashboard-region-context{margin-left:10px!important;margin-right:0!important' in css

mig = read('portal/migrations/0177_v011105_tracking_dialog_scan_height.py')
assert "version='0.11.105'" in mig
assert '0176_v011104_tracking_dialog_natural_height' in mig
print('ScoutBox 0.11.105 targeted regression checks passed')
