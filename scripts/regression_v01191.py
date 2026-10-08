from pathlib import Path

root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.91'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.91'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.91'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.91'
assert (root/'docs/RELEASE_NOTES_0.11.91.md').exists()
assert '0.11.92, 0.11.93, 0.11.94' in read('RELEASE_POLICY.md')

models=read('portal/models.py')
assert 'title_retry_count = models.PositiveSmallIntegerField' in models
assert 'title_retry_started_at = models.DateTimeField' in models
migration=read('portal/migrations/0163_v01191_retry_and_titles.py')
assert "('portal','0162_v01190_ui_consistency')" in migration
assert "version='0.11.91'" in migration
assert "validation_state='pending'" in migration

tasks=read('portal/tasks.py')
assert 'def facebook_page_title_tick' in tasks
assert 'max_attempts=4' in tasks and 'max_window=timedelta(minutes=20)' in tasks
assert "validation_state='pending'" in tasks and "validation_state='unavailable'" in tasks
assert 'def tracking_article_title_tick' in tasks
assert 'resolve_article(rule.destination_url,timeout=8)' in tasks
settings=read('opportunity_portal/settings.py')
assert "'facebook-page-title-tick': {'task':'portal.tasks.facebook_page_title_tick','schedule':300.0}" in settings
assert "'tracking-article-title-tick': {'task':'portal.tasks.tracking_article_title_tick','schedule':900.0}" in settings

facebook=read('templates/portal/facebook_pages.html')
assert "{% icon 'clock' %}" in facebook
assert 'facebook-title-retry' not in facebook
assert 'retryFacebookTitle' not in facebook
views=read('portal/views.py')
assert "action=='retry_title'" not in views
assert "tracking_article_title_tick.delay(8)" in views
assert "cache.add('tracking-article-title-refresh',True,timeout=300)" in views

tracking=read('portal/services/tracking.py')
assert 'MARKDOWN_LINK_TITLE_RE' in tracking
assert 'def clean_article_title' in tracking
assert 'def article_title_needs_refresh' in tracking
assert 'def _page_title_from_soup' in tracking
assert "if _title_is_placeholder(candidate):" in tracking
assert "{'property':'og:title'},{'name':'twitter:title'},{'name':'title'}" in tracking
assert "stored_title=clean_article_title(rule.article_title)" in tracking
links=read('templates/portal/links.html')
assert '<col class="tracking-clicks-col">' in links
assert 'tracking-created-cell' in links
assert '|tracking_article_title' in links
rules=read('templates/portal/link_rules.html')
assert 'id="tracking-docx-scan-form"' in rules
assert 'tracking-docx-scan-spinner' in rules
assert "label.textContent='Scanning…'" in rules
assert 'data-list-table data-page-size="5"' in rules
assert '<col class="tracking-scan-test-col">' in rules

telemetry=read('templates/portal/telemetry.html')
assert 'function compactDiscoveryTables()' not in telemetry
assert '<th data-nosort>Workload</th><th data-nosort>AI Usage</th><th>Errors</th><th>Avg Latency</th>' in telemetry
assert 'Events <b>{{m.events|resource_number}}</b>' in telemetry
assert 'Requests <b>{{m.requests|resource_number}}</b>' in telemetry
assert 'Pages <b>{{m.pages|resource_number}}</b>' in telemetry
assert '<th data-nosort>Results</th>' in telemetry

css=read('portal/static/portal/app.css')
for marker in (
    '.facebook-title-pending{display:inline-flex!important;align-items:center!important;justify-content:center!important;width:auto!important;height:auto!important;padding:0!important;border:0!important',
    '#tracking-table col.tracking-clicks-col{width:44px!important}',
    '#tracking-table col.tracking-created-col{width:132px!important}',
    '.tracking-docx-scan-spinner{display:inline-block',
    '.tracking-scan-results{width:100%!important;max-width:100%!important;overflow-x:auto!important',
    '.search-log-table{width:100%!important;min-width:0!important;table-layout:fixed!important}',
    '.search-log-table th:nth-child(3),.search-log-table td:nth-child(3){width:76px!important',
    '#provider-performance,#provider-history{table-layout:fixed!important;min-width:0!important',
    '.telemetry-activity-cell,.telemetry-ai-usage-cell{min-width:0!important}',
    '#usage-table th:nth-child(6),#usage-table td:nth-child(6){width:25%!important;min-width:0!important}',
):
    assert marker in css, marker

print('ScoutBox 0.11.91 regression checks passed')
