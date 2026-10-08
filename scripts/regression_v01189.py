from pathlib import Path

root = Path(__file__).resolve().parents[1]
read = lambda name: (root / name).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.89'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.89'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.89'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.89'
assert (root / 'docs/RELEASE_NOTES_0.11.89.md').exists()

views = read('portal/views.py')
assert "('-discovered_at','-pk')" in views
assert "version_option_rows.append({'value':'__unknown__'" in views
assert '_resource_chart_rows(sample_rows,qs,start,end,max_points=240)' in views
assert 'download_breakdown=download_breakdown' in views

markets = read('portal/services/discovery_markets.py')
search = read('portal/services/search.py')
discovery = read('portal/services/discovery.py')
assert 'def market_from_location' in markets
assert 'def provider_market_compatible' in search
assert 'market=target_market' in discovery
assert 'if not provider_market_compatible(provider,market)' in discovery

facebook = read('templates/portal/facebook_pages.html')
assert 'danger toolbar-icon-action' not in facebook

tracking = read('portal/services/tracking.py')
assert "rule.article_title != info['title']" in tracking
rules = read('templates/portal/link_rules.html')
assert 'new ResizeObserver' not in rules
assert 'new MutationObserver' in rules
links = read('templates/portal/links.html')
assert 'Math.min(760,requested)' in links
assert 'tracking-application-unavailable' in links
assert 'not x.application.deleted_at and not x.application.opportunity.user_deleted' in links

telemetry = read('templates/portal/telemetry.html')
assert "openModal('download-usage-modal')" in telemetry
assert 'function compactDiscoveryTables()' in telemetry
assert "market-coverage-tooltip-title" in telemetry

audit = read('templates/portal/audit.html')
assert 'audit-version-filter' in audit
assert 'Search versions…' in audit

tasks = read('portal/tasks.py')
settings = read('opportunity_portal/settings.py')
assert 'def facebook_page_title_tick' in tasks
assert 'facebook-page-title-tick' in settings

css = read('portal/static/portal/app.css')
for marker in ('#recycle-bin-table col.recycle-type-col{width:105px!important}',
               '.email-history-inline-range{position:absolute!important',
               '#telemetry-updated,.resource-meta-separator{display:none!important}',
               '.table-wrap:has(.profile-assets-table)+details.advanced',
               '.preference-pane .pay-rule{border:0!important',
               '.preference-pane .engagement-types-label{font-size:inherit!important'):
    assert marker in css

migration = read('portal/migrations/0161_v01189_consistency_repairs.py')
assert "version='0.11.89'" in migration
print('ScoutBox 0.11.89 regression checks passed')
