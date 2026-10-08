from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(p): return (root/p).read_text(encoding='utf-8')
assert read('VERSION').strip()=='0.11.101'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.101'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.101'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.101'
assert (root/'docs/RELEASE_NOTES_0.11.101.md').exists()
link=read('templates/portal/link_rules.html')
assert 'Import link' in link and 'tracking-action-field' in link and 'tracking-main-field' in link
links=read('templates/portal/links.html')
assert 'tracking-generated-suffix' in links
base=read('templates/portal/base.html')
assert 'data-date-picker' in base and 'portalResultNotice' in base and 'alignTableSearchFields' in base
gpt=read('templates/portal/gpt_log.html')
assert 'Search models…' in gpt and 'name="model"' in gpt and 'data-open-json-string' in gpt
views=read('portal/views.py')
assert "_selected_filter_values(request,'model')" in views and "show_vram_series=show_vram_series" in views
chat=read('portal/services/chatbot.py')
assert "'feature':'Facebook Pages'" in chat and "'feature':'Tracking Links'" in chat and "Open Tracking Links" in chat
tele=read('templates/portal/telemetry.html')
assert '{% if show_vram_series %}' in tele
mig=read('portal/migrations/0173_v011101_ui_chatbot_filters.py')
assert "version='0.11.101'" in mig
print('ScoutBox 0.11.101 targeted regression checks passed')
