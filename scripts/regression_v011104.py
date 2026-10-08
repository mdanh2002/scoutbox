from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(p): return (root/p).read_text(encoding='utf-8')
assert read('VERSION').strip()=='0.11.104'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.104'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.104'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.104'
assert (root/'docs/RELEASE_NOTES_0.11.104.md').exists()

css=read('portal/static/portal/app.css')
rules=read('templates/portal/link_rules.html')
links=read('templates/portal/links.html')
assert '.tracking-add-frame{height:170px!important;min-height:0!important}' in css
assert '.embedded-page .app,.embedded-page .main{min-height:0!important;height:auto!important}' in css
assert '.embedded-page .content{flex:0 0 auto!important}' in css
assert "target=editor||content||document.body" in rules
assert "rect=target?.getBoundingClientRect()" in rules
assert "padBottom=parseFloat(contentStyle?.paddingBottom||'0')||0" in rules
assert "height:Math.max(270,height)" not in rules
assert 'minimum=120' in links
assert 'Math.max(270,Math.min(available,requested))' not in links
assert "const needsScroll=requested>available+2" in links

# Preserve 0.11.103 layout and behavior as regression scope.
assert '>Short URL</label>' in rules
assert 'tracking-docx-file-input sr-only' in rules and 'tracking-docx-filename' in rules
assert '.tracking-test-button,.tracking-docx-scan-button{width:100%' in css
assert '.tracking-blog-base-line .tracking-save-base-button{flex:1 1 auto' in css
assert 'tracking-article-input{flex:0 0 112px' in css
assert '.date-range-inline>.icon-btn.active,.resource-date-form>.icon-btn.active' in css
assert '.dashboard-region-context{margin-left:10px!important;margin-right:0!important' in css

mig=read('portal/migrations/0176_v011104_tracking_dialog_natural_height.py')
assert "version='0.11.104'" in mig and '0175_v011103_tracking_date_activity_polish' in mig
print('ScoutBox 0.11.104 targeted regression checks passed')
