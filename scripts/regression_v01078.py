from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text()

def fail(message):
    raise SystemExit(f'FAIL: {message}')

if read('VERSION').strip() != '0.10.78': fail('VERSION is not 0.10.78')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.78': fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.78': fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.78'): fail('README not bumped')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.78.md').is_file(): fail('0.10.78 release notes missing')

settings = read('templates/portal/settings.html')
contacts = read('templates/portal/contacts.html')
telemetry = read('templates/portal/telemetry.html')
css = read('portal/static/portal/app.css')
views = read('portal/views.py')
tasks = read('portal/tasks.py')
fresh = read('portal/services/fresh_sources.py')
discovery = read('portal/services/discovery.py')
cold = read('portal/services/cold.py')
tests = read('portal/tests/test_v01078.py')

if '<option value="1h">Last 1 hour</option>' not in settings: fail('diagnostic 1-hour option missing')
if "if raw in {'1h','1hr','1hrs'}" not in views or "return '1h',now-timedelta(hours=1)" not in views: fail('diagnostic 1-hour backend missing')

if 'contact-company-line contact-company-link' not in contacts: fail('Address Book company link missing')
if 'c.email|email_domain_home_url' not in contacts: fail('Address Book company link is not derived from stored email')
if 'title="{{company_home|domain_name}}"' not in contacts: fail('Address Book company-domain tooltip missing')
if '.contact-company-link:hover' not in css: fail('Address Book company hover underline missing')

if '.telemetry-page .token-usage-heading,.telemetry-page .discovery-performance-heading{padding-right:12px!important}' not in css: fail('telemetry heading right edge not normalized')
if '.telemetry-page .token-legend-export,.telemetry-page .discovery-legend-export{margin-left:auto!important;margin-right:0!important' not in css: fail('telemetry export icons not aligned to identical right edge')
heading = telemetry.split('token-usage-heading', 1)[1].split('</div><div class="body">', 1)[0]
if heading.find('token-model-filter-status') > heading.find('token-legend-export'): fail('Token Usage export must remain to the right of All tokens')

for token in ('SCOUTBOX_REDDIT_MAX_QUERIES_PER_PASS','SCOUTBOX_REDDIT_PASS_MAX_SECONDS','SCOUTBOX_REDDIT_REQUEST_TIMEOUT_SECONDS','SCOUTBOX_REDDIT_MAX_CONSECUTIVE_ERRORS'):
    if token not in fresh: fail(f'Reddit stall guard missing: {token}')
if 'Reddit request error limit reached after' not in fresh or 'Reddit pass time budget reached' not in fresh: fail('Reddit fail-fast exit messages missing')
if "failure_key='scoutbox:reddit:oauth-token-failed'" not in fresh or 'cache.set(failure_key,True,300)' not in fresh: fail('Reddit OAuth failure negative-cache missing')
if "SCOUTBOX_SEARCH_PROVIDER_MAX_CONSECUTIVE_ERRORS" not in discovery: fail('normal search-provider circuit breaker missing')
if 'stopped after {consecutive_errors} consecutive request errors' not in discovery: fail('normal search-provider circuit breaker exit missing')
if 'Hidden Leads scan stopped this provider after {consecutive_errors} consecutive request errors' not in cold: fail('Hidden Leads search-provider circuit breaker missing')

if 'Recover Stalled Operations' not in settings or 'class="btn warn"' not in settings: fail('amber Maintenance recovery action missing')
if 'value="recover_stalled_operations"' not in settings or 'Type RECOVER' not in settings: fail('Maintenance recovery confirmation missing')
if 'def recover_stalled_operations_state()' not in tasks: fail('persistent-state recovery helper missing')
for token in ("status__in=['queued','running','stopping']", "status__in=['queued','running']", "terminate=True,signal='SIGTERM'", "scoutbox:local-ai:lane:*", "scoutbox:search-provider:last:*", 'run_campaign_job.delay(new_run.pk)', 'hidden_market_scan_job.delay(new_job.pk)'):
    if token not in tasks: fail(f'Maintenance recovery behavior missing: {token}')
if "elif action=='recover_stalled_operations':" not in views or "log('maintenance_recovery'" not in views: fail('Maintenance recovery view/audit wiring missing')

if 'test_reddit_fails_fast_after_repeated_request_errors' not in tests: fail('Reddit fail-fast runtime regression missing')
if 'test_hidden_leads_search_rotates_after_repeated_provider_errors' not in tests: fail('Hidden Leads provider fail-fast runtime regression missing')
if 'test_recovery_releases_persistent_state_and_requeues_safe_work' not in tests: fail('Maintenance recovery runtime regression missing')
if 'test_address_book_company_links_to_email_domain' not in tests: fail('Address Book email-domain link runtime regression missing')

print('ScoutBox 0.10.78 targeted regressions passed.')
