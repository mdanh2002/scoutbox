from pathlib import Path
import importlib.util
import sys

root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.96'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.96'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.96'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.96'
assert (root/'docs/RELEASE_NOTES_0.11.96.md').exists()
assert '0.11.97, 0.11.98, 0.11.99' in read('RELEASE_POLICY.md')

# 0.11.95 migration fix must remain intact and the new audit migration must use
# fields present in the historical AuditLog state.
m166=read('portal/migrations/0166_v01194_telemetry_ui_followups.py')
assert 'detail__contains' not in m166 and 'detail=' not in m166
m168=read('portal/migrations/0168_v01196_tracking_stats_ui.py')
assert "('portal', '0167_v01195_migration_hotfix')" in m168
assert "action='version_upgraded'" in m168 and "version='0.11.96'" in m168
assert 'detail' not in m168

# Tracking allocation: candidate URLs do not exist until after persistence, so
# network probing must not be part of allocate(). DB uniqueness is authoritative.
tracking=read('portal/services/tracking.py')
allocate=tracking[tracking.index('def allocate('):tracking.index('def allocate_for_url(')]
assert 'requests.get' not in allocate and 'requests.head' not in allocate
assert 'IntegrityError' in allocate and 'transaction.atomic()' in allocate
tasks=read('portal/tasks.py')
job=tasks[tasks.index('def tracking_link_test_job('):tasks.index('@shared_task\ndef tracking_article_title_tick')]
assert 'preview_for_url(article_url)' in job and "allocate(preview['rule'])" in job
assert 'allocate_for_url(article_url)' not in job
assert 'TrackingLink.objects.filter(path=path).exists()' in allocate
assert 'TrackingLink.objects.create' in allocate

link_rules=read('templates/portal/link_rules.html')
assert 'id="tracking-dialog-status"' in link_rules
assert "trackingStatus('Scanning DOCX links…')" in link_rules
assert "trackingStatus('URL loaded from Document Link Check. Click Test & Generate to resolve and generate it.')" in link_rules
assert "scoutbox-tracking-frame-scroll" in link_rules
assert 'tracking-blog-base-inline' in link_rules and 'tracking-docx-inline' in link_rules
links=read('templates/portal/links.html')
assert "scoutbox-tracking-frame-scroll" in links
assert "scrolling=\"no\"" in links

css=read('portal/static/portal/app.css')
assert '#tracking-table col.tracking-clicks-col{width:64px!important}' in css
assert '.tracking-blog-base-inline{display:flex!important' in css
assert '.embedded-page{overflow-x:hidden!important;overflow-y:hidden!important}' in css

# Statistics / Resource Usage default to 24 hours and the duplicate Discovery
# Source table is gone while the chart remains.
views=read('portal/views.py')
period=views[views.index('def _period_bounds('):views.index('def _resource_period_bounds(')]
resource=views[views.index('def _resource_period_bounds('):views.index('def _log_date_bounds(')]
for section in (period,resource):
    assert "or '24h'" in section
    assert "period='24h'; start=now-timedelta(hours=24)" in section
stats=read('templates/portal/stats.html')
assert '<h3>Discovery Source Share</h3>' in stats
assert 'source-summary-data' in stats
assert '<h3>Discovery Source</h3>' not in stats

# User-facing timestamp labels are consistently Time.
for name in ('templates/portal/email_history.html','templates/portal/gpt_log.html','templates/portal/search_log.html'):
    text=read(name)
    assert '>Time<' in text

# Market localization rotates major cities and retains a periodic country-wide pass.
spec=importlib.util.spec_from_file_location('discovery_markets_v01196', root/'portal/services/discovery_markets.py')
module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module)
au=module.MARKET_BY_CODE['au']
queries=[module.market_query('software engineer opening',au,rotation_offset=i) for i in range(6)]
assert queries[0].endswith(' in Melbourne')
assert queries[1].endswith(' in Sydney')
assert queries[2].endswith(' in Brisbane')
assert queries[3].endswith(' in Perth')
assert queries[4].endswith(' in Adelaide')
assert queries[5].endswith(' Australia') and ' in Australia' not in queries[5]
assert module.market_query('software engineer Australia opening',au,0)=='software engineer Melbourne opening'
assert module.market_query('software engineer opening',module.MARKET_BY_CODE['sg'],0).endswith(' Singapore')

discovery=read('portal/services/discovery.py')
assert discovery.count('market_query(')>=3
assert 'rotation_offset=rotation_offset+idx' in discovery

# Dashboard broad counters replace the old narrow workflow-status cards and are
# included in live refreshes in the requested order.
dash=read('templates/portal/dashboard.html')
labels=['New opportunities','New Hidden Leads','Address Book','Facebook Pages','Applications &amp; Outreaches','Replies today','Errors · 24h']
pos=[dash.index(label) for label in labels]
assert pos==sorted(pos)
for key in ('address_book','facebook_pages','applications'):
    assert f'dash-stat-{key.replace("_","-")}' in dash
    assert f"'{key}'" in dash
stat_fn=views[views.index('def _dashboard_stats('):views.index('def _capture_resource_sample(')]
for key in ('address_book','facebook_pages','applications'):
    assert f"'{key}'" in stat_fn
assert "Q(generic=False)|Q(source__iexact='manual')" in stat_fn
assert "FacebookPage.objects.filter(deleted_at__isnull=True).count()" in stat_fn
assert "'apply'" not in stat_fn and "'review'" not in stat_fn and "'info'" not in stat_fn

# Campaigns and Templates share one search and toolbar geometry.
campaigns=read('templates/portal/campaigns.html')
assert campaigns.count('class="searchbox campaign-tab-search"')==2
assert campaigns.count('campaign-tab-toolbar')==2
assert 'searchbox compact-list-search" data-table-filter="campaign-table"' not in campaigns
assert 'class="campaign-tab-panel"' in campaigns
assert '.campaign-tab-search{width:360px!important' in css
assert '.campaign-list-card,.campaign-template-list-card{margin:0!important}' in css

print('ScoutBox 0.11.96 targeted regression checks passed')
