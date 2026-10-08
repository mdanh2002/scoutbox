from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.146'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.146'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.146'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.146'
assert (root/'docs/RELEASE_NOTES_0.11.146.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-10-01 10:20:00'" in read('opportunity_portal/settings.py')
assert 'The release following 0.11.146 is 0.11.147' in read('RELEASE_POLICY.md')

template=read('templates/portal/settings.html')
assert 'modal-card modal-form diagnostic-export-modal-card' in template
css=read('portal/static/portal/app.css')
assert '.diagnostic-export-modal-card{width:min(540px,calc(100vw - 28px));max-width:min(540px,calc(100vw - 28px))}' in css

migration=read('portal/migrations/0218_v011146_diagnostic_export_modal_width.py')
assert "dependencies=[('portal','0217_v011145_resource_usage_panel_cleanup')]" in migration
assert "version='0.11.146'" in migration
assert "'diagnostic_export_modal_compacted':True" in migration

# Existing fixes remain packaged.
for name in [
    '0217_v011145_resource_usage_panel_cleanup.py',
    '0216_v011144_telemetry_continuity.py',
    '0215_v011143_restart_recovery.py',
    '0214_v011142_facebook_page_title_wrap.py',
    '0213_v011141_source_coverage_integrity.py',
]:
    assert (root/'portal/migrations'/name).exists()
assert 'ScoutBox/0.11.146' in read('portal/services/search.py')

print('ScoutBox 0.11.146 targeted regression checks passed')
