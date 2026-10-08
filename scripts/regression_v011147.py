from pathlib import Path
import ast
import re

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.147'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.147'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.147'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.147'
assert (root/'docs/RELEASE_NOTES_0.11.147.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-10-01 10:45:00'" in read('opportunity_portal/settings.py')
assert 'The release following 0.11.147 is 0.11.148' in read('RELEASE_POLICY.md')

# Balanced discovery is niche-campaign aware; Broad remains the explicit wide-net mode.
selectivity=read('portal/services/selectivity.py')
assert "'balanced': {'confidence': 70, 'relevance_confidence': 65, 'fit_score': 55" in selectivity
assert "'balanced': {'semantic_delta': 0, 'minibrowser_cutoff': 80" in selectivity
assert "'requires_campaign_anchor': True" in selectivity
assert 'def campaign_alignment(' in selectivity
links=read('portal/services/campaign_links.py')
assert "reason':'missing_campaign_specific_evidence'" in links
assert 'fail closed rather than polluting a niche' in links

# Google Jobs gets job intent only; SearchAPI's dedicated location/gl/hl remains active.
discovery=read('portal/services/discovery.py')
assert 'def _google_jobs_query_text(query_item):' in discovery
assert "re.sub(r'(?i)\\bsite:\\S+'" in discovery
assert "provider_query" in discovery and "base_query" in discovery
search=read('portal/services/search.py')
assert "params={'engine':engine,'q':query,**_searchapi_locale(market,source)}" in search
assert "params={'gl':str(meta.get('country_code')" in search
assert "params['location']=location" in search
# Execute the isolated helper to make sure market-appended text/site scopes are not leaked.
tree=ast.parse(discovery)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_google_jobs_query_text')
ns={'re':re}; exec(compile(ast.Module(body=[fn],type_ignores=[]),'<google-jobs-helper>','exec'),ns)
clean=ns['_google_jobs_query_text']({'query':'site:workable.com "firmware engineer" Egypt','base_query':'site:workable.com "firmware engineer"','provider_query':'site:workable.com "firmware engineer"'})
assert clean=='"firmware engineer"',clean

# Multilingual syntax is normalized and separately observable.
assert "stage='multilingual_translation'" in discovery
assert "stage='multilingual_page_translation'" in discovery
assert "if translated.count('\\\"') % 2" in discovery

# Direct-source acquisition fairness continues through the pre-AI candidate cap.
fresh=read('portal/services/fresh_sources.py')
assert 'qualification_floor_by_source' in fresh
assert 'qualification_selected_by_source' in fresh
assert 'qualification_dropped_by_source' in fresh
assert "'yc_jobs'" in fresh

# Large filter selections are POSTed to a session-scoped token before any oversized GET.
settings=read('opportunity_portal/settings.py')
assert "'portal.middleware.FilterStateMiddleware'" in settings
middleware=read('portal/middleware.py')
assert "SESSION_KEY = 'scoutbox_filter_states_v1'" in middleware
assert "request.GET = restored" in middleware
views=read('portal/views.py')
assert 'def save_list_filter_state(request):' in views
assert "len(raw_query)>65536" in views
base=read('templates/portal/base.html')
assert 'async function compactScoutBoxFilterUrl(url)' in base
assert "target.toString().length<=1800" in base
assert "fetch('/filters/state/'" in base
assert "document.addEventListener('submit',async event=>" in base
extras=read('portal/templatetags/portal_extras.py')
assert 'def _compact_filter_params(request):' in extras
assert "params['fs']=token" in extras

# Diagnostic export is granular, size-aware, and keeps the narrower 0.11.146 dialog.
settings_html=read('templates/portal/settings.html')
for key in ('context','opportunities','hidden_leads','contacts','facebook','search','discovery','ai','resources','operations'):
    assert f'name="category" value="{key}"' in settings_html
    assert f'data-diagnostic-size="{key}"' in settings_html
assert 'Estimated total before compression:' in settings_html
assert 'refreshDiagnosticExportEstimate()' in settings_html
assert 'def diagnostic_export_estimate(request):' in views
assert "'granular_export'" in views
assert "scope_name=('selected' if category_mode" in views
css=read('portal/static/portal/app.css')
assert '.diagnostic-export-modal-card{width:min(540px,calc(100vw - 28px));max-width:min(540px,calc(100vw - 28px))}' in css

migration=read('portal/migrations/0219_v011147_discovery_quality_and_diagnostics.py')
assert "dependencies=[('portal','0218_v011146_diagnostic_export_modal_width')]" in migration
assert "version='0.11.147'" in migration
assert "'granular_diagnostic_export':True" in migration
assert 'ScoutBox/0.11.147' in search
assert 'ScoutBox/0.11.147' in fresh

print('ScoutBox 0.11.147 targeted regression checks passed')
