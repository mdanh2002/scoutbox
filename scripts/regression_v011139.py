from pathlib import Path
import importlib.util
import sys

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.139'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.139'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.139'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.139'
assert (root/'docs/RELEASE_NOTES_0.11.139.md').exists()
assert "PORTAL_LAST_MODIFIED = '2026-09-28 19:16:00'" in read('opportunity_portal/settings.py')

# Dependency-light company validator/ATS identity behavior.
spec=importlib.util.spec_from_file_location('v011139_platforms',root/'portal/services/platforms.py')
platforms=importlib.util.module_from_spec(spec); sys.modules[spec.name]=platforms; spec.loader.exec_module(platforms)
for bad in ('What we','What we offer','Who we are','We are','About us','The role','profitable and growing. We are'):
    assert not platforms.is_plausible_company_name(bad), bad
for good in ('Canonical','Proton','Acme Robotics'):
    assert platforms.is_plausible_company_name(good), good
assert platforms.company_from_ats_url('https://job-boards.greenhouse.io/canonical/jobs/6643483')=='Canonical'
assert platforms.company_from_ats_url('https://job-boards.eu.greenhouse.io/proton/jobs/4941344101')=='Proton'
assert platforms.company_from_ats_url('https://jobs.lever.co/acme/123')=='Acme'

# Direct-source/ATS identity must outrank local AI company extraction.
discovery=read('portal/services/discovery.py')
assert 'authoritative_direct_company=bool(' in discovery
assert "direct_company_adapters={" in discovery
assert "and not structured_company and not authoritative_direct_company" in discovery
assert "company_identity_source='jobposting_schema'" in discovery
assert "facts['company_identity']" in discovery
assert "company_from_ats_url(search_url)" in discovery
fresh=read('portal/services/fresh_sources.py')
assert 'company_from_ats_url(raw) or (company if is_plausible_company_name(company)' in fresh
assert "ScoutBox/0.11.139" in fresh
assert "ScoutBox/0.11.139" in read('portal/services/search.py')

# Generic company boilerplate must not win the visible role summary.
highlights=read('portal/services/highlights.py')
assert '_COMPANY_BOILERPLATE_PATTERNS' in highlights
assert 'not _looks_like_company_boilerplate(text)' in highlights
assert 'not _looks_like_company_boilerplate(stored)' in highlights
spec=importlib.util.spec_from_file_location('v011139_highlights',root/'portal/services/highlights.py')
h=importlib.util.module_from_spec(spec); sys.modules[spec.name]=h; spec.loader.exec_module(h)
boiler=('Canonical is a leading provider of open source software and operating systems to the global enterprise '
        'and technology markets. Our platform, Ubuntu, is very widely used in public cloud and engineering innovation.')
role='Lead firmware development for embedded Linux devices, including board bring-up, device drivers, secure boot, and C/C++ systems work.'
assert h.ai_result_fit_summary({'highlight':boiler})==''
assert h.ai_result_fit_summary({'highlight':role})
assert 'firmware' in h.opportunity_specific_highlight(result={'highlight':boiler},title='Firmware Engineer',description=boiler+' '+role).lower()

migration=read('portal/migrations/0211_v011139_company_identity_integrity.py')
assert "dependencies=[('portal','0210_v011138_searchapi_credential_reliability')]" in migration
assert "'ats_board_repair'" in migration
assert "row.company_intel={}" in migration
assert "version='0.11.139'" in migration

# Hidden Lead detail: no task/KPI strip, compact fields, Added/Source rows below Campaign.
lead=read('templates/portal/hidden_lead_detail.html')
assert 'detail-status-row' not in lead
assert 'stat-kpi-grid opportunity-kpis' not in lead
assert '<b>Status</b><b' not in lead
assert 'detail-compact-form-row' in lead
campaign_i=lead.index('<b>Campaign</b>'); added_i=lead.index('<b>Added</b>'); source_i=lead.index('<b>Source</b>'); source_url_i=lead.index('<b>Source URL</b>')
assert campaign_i < added_i < source_i < source_url_i

# Opportunity detail: status and KPI cards gone; rows reordered and fit signal moved right.
opp=read('templates/portal/opportunity_detail.html')
assert 'status-kpi' not in opp
assert 'stat-kpi-grid opportunity-kpis' not in opp
assert 'post-age-kpi' not in opp
assert 'remote-kpi' not in opp
assert 'id="post-age-row"' in opp
assert 'detail-inline-remote' in opp
assert opp.index('<b>Campaign</b>') < opp.index('<b>Added</b>') < opp.index('<b>Channel</b>') < opp.index('<b>Source URL</b>')
assert opp.index('<b>Job country</b>') < opp.index('<b>Post age</b>') < opp.index('<b>Remote</b>')
fit=opp[opp.index('<div class="kv fit-detail-row">'):opp.index('</form></div>',opp.index('<div class="kv fit-detail-row">'))]
assert fit.index('<select') < fit.index('fit-detail-signal')
assert "getElementById('post-age-row')" in opp
assert "getElementById('post-age-kpi')" not in opp

css=read('portal/static/portal/app.css')
assert '.detail-compact-form-row{grid-template-columns:180px minmax(0,260px)!important}' in css
assert '.detail-inline-remote .remote-status-display' in css
assert '.post-age-inline{display:inline-flex' in css

# Existing SearchAPI/worldwide/re-evaluation features remain present.
search=read('portal/services/search.py')
assert "SEARCHAPI_ACCOUNT_ENDPOINT='https://www.searchapi.io/api/v1/me'" in search
assert "return max(0,min(10000,int(getattr(cfg,'searchapi_daily_limit',500))))" in search
dm_spec=importlib.util.spec_from_file_location('v011139_discovery_markets',root/'portal/services/discovery_markets.py')
dm=importlib.util.module_from_spec(dm_spec); sys.modules[dm_spec.name]=dm; dm_spec.loader.exec_module(dm)
assert len(dm.DEFAULT_MARKET_CODES)>=190
for code in ('us','gb','au','sg','hk','jp','kr','cn','tw','ng','ke','br','mx'):
    assert code in dm.MARKET_BY_CODE, code

tasks=read('portal/tasks.py')
assert 'MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD = 3' in tasks
assert 'def _bounded_parallel_futures' in tasks

print('ScoutBox 0.11.139 targeted regression checks passed')
