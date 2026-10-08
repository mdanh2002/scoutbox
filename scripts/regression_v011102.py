from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(p): return (root/p).read_text(encoding='utf-8')
assert read('VERSION').strip()=='0.11.102'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.102'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.102'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.102'
assert (root/'docs/RELEASE_NOTES_0.11.102.md').exists()

link=read('templates/portal/link_rules.html')
css=read('portal/static/portal/app.css')
assert 'Import link' in link and 'tracking-action-field' in link and 'tracking-main-field' in link
assert "generated_base_url" in link and "generated_suffix" in link and "tracking-generated-suffix" in link
assert '--tracking-action:154px' in css and 'tracking-article-input{flex:0 0 132px' in css
assert '@media(max-width:560px){.tracking-editor-line,.tracking-docx-inline{grid-template-columns:1fr' in css

tasks=read('portal/tasks.py')
assert "'generated_base_url':" in tasks and "'generated_suffix':link.suffix" in tasks

base=read('templates/portal/base.html')
assert "initial.period!=='all'" in base and "period.value='custom'" in base and "period.value='all'" in base
stats=read('templates/portal/stats.html')
tele=read('templates/portal/telemetry.html')
assert "name=\"period\" value=\"{{period|default:'all'}}\"" in stats
assert "name=\"period\" value=\"{{period|default:'all'}}\"" in tele

views=read('portal/views.py')
assert 'def _capture_resource_sample(force=False, allow_stale_fallback=True):' in views
assert 'current_resource_sample=_capture_resource_sample(force=True,allow_stale_fallback=False)' in views
assert "show_vram_series=bool(current_resource_sample and (getattr(current_resource_sample,'gpu_vram_total_mb',None) or 0)>0)" in views
assert "'show_vram_series':show_vram_series" in views
assert 'data-vram-series-control' in tele and 'vramHardwareAvailable' in tele
assert "if(vramHardwareAvailable)line('gpu_vram_percent'" in tele

# Preserve already-completed 0.11.101 scope as regression coverage.
links=read('templates/portal/links.html')
assert 'tracking-generated-suffix' in links
gpt=read('templates/portal/gpt_log.html')
assert 'Search models…' in gpt and 'name="model"' in gpt and 'data-open-json-string' in gpt
assert "_selected_filter_values(request,'model')" in views
chat=read('portal/services/chatbot.py')
assert "'feature':'Facebook Pages'" in chat and "'feature':'Tracking Links'" in chat and 'Open Tracking Links' in chat
assert 'portalResultNotice' in base and 'alignTableSearchFields' in base and 'data-date-picker' in base

mig=read('portal/migrations/0174_v011102_tracking_filter_vram_followups.py')
assert "version='0.11.102'" in mig and "0173_v011101_ui_chatbot_filters" in mig
print('ScoutBox 0.11.102 targeted regression checks passed')
