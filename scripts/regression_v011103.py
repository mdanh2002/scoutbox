from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(p): return (root/p).read_text(encoding='utf-8')
assert read('VERSION').strip()=='0.11.103'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.103'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.103'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.103'
assert (root/'docs/RELEASE_NOTES_0.11.103.md').exists()

link=read('templates/portal/link_rules.html')
css=read('portal/static/portal/app.css')
assert '>Short URL</label>' in link and '>Article / short path</label>' not in link
assert 'tracking-docx-file-input sr-only' in link and 'tracking-docx-filename' in link
assert "file?.files?.[0]?.name||'No file selected.'" in link
assert '.tracking-test-button,.tracking-docx-scan-button{width:100%' in css
assert '.tracking-blog-base-line .tracking-save-base-button{flex:1 1 auto' in css
assert 'tracking-article-input{flex:0 0 112px' in css
assert '.tracking-file-field{width:100%' in css and '.tracking-docx-filename{display:block' in css
assert '.tracking-generated-suffix{font-style:italic' in css

stats=read('templates/portal/stats.html')
tele=read('templates/portal/telemetry.html')
for text in (stats,tele):
    assert "{% if period != 'all' %} active{% endif %}" in text
    assert "aria-pressed=\"{% if period != 'all' %}true{% else %}false{% endif %}\"" in text
assert '.date-range-inline>.icon-btn.active,.resource-date-form>.icon-btn.active' in css
base=read('templates/portal/base.html')
assert "const active=(period?.value||'all')!=='all'" in base
assert "Date range filter active — click to clear if unchanged" in base
assert "period.value='custom'" in base and "period.value='all'" in base

dash=read('templates/portal/dashboard.html')
assert 'dashboard-region-context' in dash
assert '.dashboard-region-context{margin-left:10px!important;margin-right:0!important' in css

# Preserve the preceding release fixes as regression scope.
tasks=read('portal/tasks.py')
assert "'generated_base_url':" in tasks and "'generated_suffix':link.suffix" in tasks
views=read('portal/views.py')
assert 'current_resource_sample=_capture_resource_sample(force=True,allow_stale_fallback=False)' in views
assert "show_vram_series=bool(current_resource_sample and (getattr(current_resource_sample,'gpu_vram_total_mb',None) or 0)>0)" in views
chat=read('portal/services/chatbot.py')
assert "'feature':'Facebook Pages'" in chat and "'feature':'Tracking Links'" in chat

mig=read('portal/migrations/0175_v011103_tracking_date_activity_polish.py')
assert "version='0.11.103'" in mig and '0174_v011102_tracking_filter_vram_followups' in mig
print('ScoutBox 0.11.103 targeted regression checks passed')
