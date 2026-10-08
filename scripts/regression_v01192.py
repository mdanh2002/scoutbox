from pathlib import Path

root=Path(__file__).resolve().parents[1]
read=lambda name:(root/name).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.92'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.92'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.92'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.92'
assert (root/'docs/RELEASE_NOTES_0.11.92.md').exists()
assert '0.11.93, 0.11.94, 0.11.95' in read('RELEASE_POLICY.md')

migration=read('portal/migrations/0164_v01192_followup_repairs.py')
assert "('portal','0163_v01191_retry_and_titles')" in migration
assert "validation_state='pending'" in migration
assert "version='0.11.92'" in migration

tracking=read('portal/services/tracking.py')
assert "def article_title_needs_refresh(value, destination_url='', rule_name='', base_path=''):" in tracking
assert "comparisons.append(_title_key(rule_name))" in tracking
assert "def _page_title_from_soup(soup, page_url=''):" in tracking
assert "if cleaned and slug_key and _title_key(cleaned)==slug_key:" in tracking
assert "title=_page_title_from_soup(soup,final)" in tracking

tasks=read('portal/tasks.py')
assert 'def tracking_article_title_tick' in tasks
assert "article_title_needs_refresh(rule.article_title,rule.destination_url,rule.name,rule.base_path)" in tasks
assert 'def facebook_page_title_tick' in tasks
assert 'facebook_page_identity_title' in tasks
assert "facebook_page_relevant(url,'',page.evidence_text" not in tasks
assert 'max_attempts=4' in tasks and 'max_window=timedelta(minutes=20)' in tasks

search=read('portal/services/search.py')
assert 'def facebook_page_identity_title' in search
assert "'source':'page_id'" in search
assert 'def _facebook_identity_from_evidence' in search

views=read('portal/views.py')
assert "cache.add('facebook-page-title-refresh',True,timeout=120)" in views
assert "article_title_needs_refresh(row.article_title,row.destination_url,row.name,row.base_path)" in views
assert "_filter_options_label('Outcomes'" in views
assert "resource_samples=list(resource_qs.order_by('-at')[:5000])" in views
assert 'resource_samples.reverse()' in views
assert "'matching_sample_count':resource_sample_total" in views
assert "'exported_first_at':resource_export_first_at" in views
assert "'exported_last_at':resource_export_last_at" in views
assert "'_synthetic_usage':bool(synthetic_usage)" in views
assert "'synthetic_usage':bool(row.get('_synthetic_usage'))" in views
assert 'Never downsample the hardware rows again.' in views

application=read('portal/services/application.py')
assert 'def scan_docx_links' in application
assert "base_host=(base.hostname or '').lower().removeprefix('www.')" in application
assert 'if not host or host!=base_host:' in application
assert "if base_path!='/' and not (path==base_path or path.startswith(base_path+'/')):" in application

rules=read('templates/portal/link_rules.html')
assert '<th>Link</th><th>Page title</th><th data-nosort>Test</th>' in rules
assert 'tracking-scan-result-col' not in rules
assert 'Trackable' not in rules and 'Not a ToughDev article' not in rules
assert 'tracking-docx-scan-spinner' in rules and "label.textContent='Scanning…'" in rules
assert 'tracking-scan-test-cell' in rules

links=read('templates/portal/links.html')
assert '{% tracking_article_display x.rule as article_display %}' in links
assert 'toolbar-actions-right tracking-actions' in links
positions=[links.index('form="tracking-sync"'),links.index("confirmRecycleDelete(this.form,'link_ids'"),links.index('show-deleted-toggle'),links.index("openModal('tracking-add-modal')")]
assert positions==sorted(positions)
assert 'btn small danger toolbar-icon-action' not in links
assert 'tracking-footer-count' in links

facebook=read('templates/portal/facebook_pages.html')
assert 'toolbar-actions-right facebook-pages-actions' in facebook
assert 'Seen/New status' not in facebook
assert 'Filter Facebook Pages by review state' in facebook
assert 'facebook-footer-count' in facebook
assert '|normalize_evidence_ellipsis' in facebook

extras=read('portal/templatetags/portal_extras.py')
assert 'def tracking_article_display(rule):' in extras
assert 'def normalize_evidence_ellipsis(value):' in extras

blacklist=read('templates/portal/blacklist.html')
assert '<col class="blacklist-scope-col"><col class="blacklist-added-col">' in blacklist

email_history=read('templates/portal/email_history.html')
email_config=read('templates/portal/email_config.html')
assert 'content="light"' in email_history
assert 'background:#fff' in email_history
assert 'color-scheme:dark!important' not in email_history
assert 'content="light"' in email_config
assert 'body *{box-sizing:border-box}' in email_config
assert 'body *{box-sizing:border-box;color:' not in email_config

telemetry=read('templates/portal/telemetry.html')
assert 'function compactDiscoveryTables()' not in telemetry
assert 'synthetic_usage' in telemetry
assert 'hardwareGapLimit' in telemetry
assert 'if(nullable&&row.synthetic_usage)return' in telemetry
assert 'downsampleResourceRows(next,480)' in telemetry
assert '<th data-nosort>Workload</th><th data-nosort>AI Usage</th><th>Errors</th><th>Avg Latency</th>' in telemetry

css=read('portal/static/portal/app.css')
for marker in (
    '#tracking-docx-table th:nth-child(3),#tracking-docx-table td:nth-child(3){width:58px!important',
    '.tracking-actions .show-deleted-toggle .svg-icon,.facebook-pages-actions .show-deleted-toggle .svg-icon',
    '.search-log-table th:nth-child(6),.search-log-table td:nth-child(6){width:184px!important',
    '.search-log-query-text{display:block!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important',
    '#provider-performance th:nth-child(4){padding-right:30px!important',
    '#blacklist-table col.blacklist-scope-col{width:86px}',
    '#blacklist-table col.blacklist-added-col{width:168px}',
    '.email-preview-frame,.imap-email-preview-frame{background:#fff!important;color-scheme:light!important}',
    '.email-history-count{font-weight:400!important;margin-right:14px!important}',
):
    assert marker in css, marker

print('ScoutBox 0.11.92 regression checks passed')
