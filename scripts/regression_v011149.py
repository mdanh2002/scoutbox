from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.149'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.149'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.149'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.149'
assert 'The release following 0.11.149 is 0.11.150' in read('RELEASE_POLICY.md')
assert "PORTAL_LAST_MODIFIED = '2026-10-01 12:25:00'" in read('opportunity_portal/settings.py')

css=read('portal/static/portal/app.css')
assert 'grid-template-columns:110px minmax(0,1fr)!important' in css
assert 'padding-right:16px!important' in css
assert '.diagnostic-export-period-row select{width:230px!important;max-width:230px!important;justify-self:end!important}' in css
assert '.diagnostic-export-estimate-total b{margin-left:auto;color:#f2f8fc;font-size:13px;font-weight:800' in css
assert '.diagnostic-export-estimate-total + .section-actions{margin-top:16px!important}' in css
assert 'padding-right:0!important' in css and 'justify-self:stretch!important' in css

settings=read('templates/portal/settings.html')
assert 'Total (uncompressed)' in settings
assert 'Last 24 hours' in settings
assert 'Prepare ZIP' in settings and 'Cancel' in settings

# Guard against accidental functional edits to the 0.11.148 Search Activity contract.
html=read('templates/portal/search_log.html')
assert 'name="market"' in html and 'name="query_language"' in html
assert 'name="region"' not in html
search=read('portal/services/search.py')
assert "metadata.update(query_language_metadata(query_language))" in search
assert 'ScoutBox/0.11.149' in search

migration=read('portal/migrations/0221_v011149_diagnostic_export_layout_polish.py')
assert "dependencies=[('portal','0220_v011148_search_activity_language_semantics')]" in migration
assert "version='0.11.149'" in migration
assert "'presentation_only':True" in migration
print('ScoutBox 0.11.149 targeted regression checks passed')
