from pathlib import Path

root = Path(__file__).resolve().parents[1]
read = lambda name: (root / name).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.90'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.90'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.90'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.90'
assert (root / 'docs/RELEASE_NOTES_0.11.90.md').exists()

views = read('portal/views.py')
resource_bounds = views[views.index('def _resource_period_bounds'):views.index('def _log_date_bounds')]
assert 'start=now-rolling[period]; end=now' in resource_bounds
assert "['Provider Type','Provider','Region','Query','Status','Results','Latency ms','Size bytes','Error','Date']" in views
assert "['Version','Actor','Action','Object type','Object id','Summary','Time']" in views
assert "['Item Title','Item Info','Item Type','Item Date','Date Deleted']" in views
assert 'clean_blacklist_reason(x.reason)' in views

blacklist = read('portal/services/blacklist.py')
assert 'def clean_blacklist_reason' in blacklist
assert r'Added from (?:Hidden Leads?|Opportunities|Recycle Bin)' in blacklist
migration = read('portal/migrations/0162_v01190_ui_consistency.py')
assert "version='0.11.90'" in migration

facebook = read('templates/portal/facebook_pages.html')
assert 'is-new is-active' in facebook and 'is-seen is-active' in facebook
assert 'facebook-title-retry' in facebook and 'retryFacebookTitle' in facebook
tasks = read('portal/tasks.py')
assert "validation_state='unavailable'" in tasks
assert 'facebook_page_title_tick' in tasks

links = read('templates/portal/links.html')
rules = read('templates/portal/link_rules.html')
assert 'tracking-list-card' in links
assert 'Math.min(620,available,requested)' in links
assert 'data-page-size="5"' in rules
assert 'tracking-scan-single-line' in rules

search = read('templates/portal/search_log.html')
assert search.index('>Provider</a>') < search.index('>Date</a>')
gpt = read('templates/portal/gpt_log.html')
assert gpt.index('>Task / Related</a>') < gpt.index('>Date</a>')
audit = read('templates/portal/audit.html')
assert audit.index('<th>Version</th>') < audit.index('<th>Time</th>')
assert 'Mail history is available under' not in audit
email = read('templates/portal/email_history.html')
assert email.index('<th data-sortable>Server</th>') < email.index('<th data-sortable>When</th>')
assert 'email-history-top-count' in email
recycle = read('templates/portal/recycle_bin.html')
assert recycle.index('>Item Title</a>') < recycle.index('>Item Date</a>') < recycle.index('>Date Deleted</a>')

telemetry = read('templates/portal/telemetry.html')
assert 'function compactDiscoveryTables()' in telemetry
assert '<th data-nosort>Usage</th>' in telemetry
assert "['provider-performance',[0,1,2,7,8,6,9]" in telemetry
assert "['provider-history',[0,1,2,3,8,9,7,10]" in telemetry

search_service = read('portal/services/search.py')
assert 'Naver deliberately remains global here' in search_service
assert "allowed={'Baidu':{'hk'}}.get(name)" in search_service
markets = read('portal/services/discovery_markets.py')
assert "if market.code=='worldwide' or pages>0 or retained>0" not in markets
assert 'Treat Worldwide like every other market' in markets

css = read('portal/static/portal/app.css')
for marker in (
    '#first-run-readiness .readiness-selectivity-links{font-size:inherit!important',
    '.facebook-page-id-link{text-decoration:none!important',
    '.tracking-add-modal-card{height:auto!important',
    '.telemetry-page #token-providers>.body',
    '.resource-metrics-grid .metric:hover,.resource-metrics-grid .metric:focus-visible{border-color:#67c9ef!important',
    '.email-history-top-count{position:static!important',
    '#recycle-bin-table col.recycle-type-col{width:125px!important',
):
    assert marker in css

print('ScoutBox 0.11.90 regression checks passed')
