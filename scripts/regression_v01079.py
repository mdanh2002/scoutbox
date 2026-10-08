from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def fail(message):
    raise SystemExit(f'FAIL: {message}')


if read('VERSION').strip() != '0.10.79': fail('VERSION is not 0.10.79')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.79': fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.79': fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.79'): fail('README not bumped')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.79.md').is_file(): fail('0.10.79 release notes missing')

compose = read('docker-compose.yml')
nvidia = read('docker-compose.nvidia.yml')
cpu = read('docker-compose.cpu-ollama.yml')
restart = read('restart_scout_box.sh')
smoke = read('scripts/smoke.sh')
tasks = read('portal/tasks.py')
discovery = read('portal/services/discovery.py')
fresh = read('portal/services/fresh_sources.py')
search = read('portal/services/search.py')
ai = read('portal/services/ai.py')
cloud = read('portal/services/cloud_discovery.py')
cold = read('portal/services/cold.py')
mailbox = read('portal/services/mailbox.py')
migration = read('portal/migrations/0108_v01079_contact_generic_repair.py')
tests = read('portal/tests/test_v01079.py')

# Forum throughput isolation / startup wiring.
for token in ('forum_worker:', '--queues=forum', '--concurrency=1', '--prefetch-multiplier=1'):
    if token not in compose: fail(f'dedicated Forum worker missing: {token}')
if 'forum_worker:' not in nvidia or 'forum_worker:' not in cpu: fail('Forum worker missing from Ollama Compose overlays')
if 'dc up -d worker discovery_worker forum_worker beat' not in restart: fail('restart/upgrade does not start Forum worker')
if 'Forum worker service' not in smoke: fail('smoke test does not verify Forum worker service')
for token in ("queue='forum'", 'SCOUTBOX_FORUM_GLOBAL_INTERVAL_MINUTES', 'SCOUTBOX_FORUM_BROWSE_INTERVAL_MINUTES', 'higher_priority_background_work', 'primary_throughput_isolated'):
    if token not in tasks: fail(f'Forum scheduler isolation missing: {token}')
if "exclude(criteria__forum_only=True)" not in tasks: fail('Forum runs are not excluded from primary campaign counters')
if "forum_only':forum_only" not in tasks: fail('Forum usage context is not propagated to AI routing')
if 'forum_yielded_local_ai' not in tasks or 'forum_yielded_cloud_rate_limit' not in tasks: fail('Forum resource-yield handling missing')
if "BackgroundJob.objects.filter(status__in=['queued','running']).exists()" not in tasks:
    fail('Forum task does not yield to every active BackgroundJob')
if "BackgroundJob.objects.filter(status__in=['queued','running']).count()" not in tasks:
    fail('Forum scheduler does not wait for all background work to become idle')
if "not item.get('forum_only')" not in tasks:
    fail('Forum-only scheduling can overwrite the primary last-discovery timestamp')

# Concrete Forum bug and strict bounded work.
if 'def forum_source_rows(campaign, search_profile=None, *, limit=60, test=False, progress_callback=None, should_stop=None, stage_budget_seconds=None, max_sources=None):' not in fresh:
    fail('forum_source_rows stage/source budget signature regression')
for token in ('SCOUTBOX_FORUM_ONLY_STAGE_MAX_SECONDS', 'SCOUTBOX_FORUM_SOURCES_PER_PASS', 'SCOUTBOX_FORUM_CLOUD_QUALIFICATION_MAX', 'SCOUTBOX_FORUM_LOCAL_QUALIFICATION_MAX'):
    if token not in discovery: fail(f'Forum pass bound missing: {token}')
cloud_primary = discovery.split('def _run_cloud_native_campaign', 1)[1].split('def _company_career_page_records', 1)[0]
if 'forum_source_rows(' in cloud_primary: fail('Forum acquisition runs inline in primary Cloud Web path')
local_primary = discovery.split("if mode != 'source_guided':", 1)[1]
# There is a Forum helper earlier in the module; the main source-guided branch must describe isolation instead of calling it.
if "Forum discovery runs independently on the forum queue" not in local_primary: fail('Local primary path does not isolate Forum acquisition')

# AI priority: Forum must never sit ahead of primary work on scarce capacity.
for token in ("forum_only = bool(ctx.get('forum_only'))", 'single non-blocking lane-acquisition attempt', 'SCOUTBOX_FORUM_LOCAL_AI_TIMEOUT_SECONDS', 'SCOUTBOX_FORUM_CLOUD_AI_TIMEOUT_SECONDS', 'ordered=ordered[:1]', "exclude(metadata__forum_only=True)", "if bool(ctx.get('forum_only')):"):
    if token not in ai: fail(f'Forum AI priority guard missing: {token}')
if 'cloud_web_search(prompt, timeout=180' not in cloud: fail('Cloud direct/Forum qualification does not use resilient Cloud route')

# Adaptive search/direct balancing from recent yield + current retention.
for token in ('def _recent_provider_health_map', 'active_records', 'discarded_records', 'retention_rate', 'provider_query_allowance', 'At most one' ):
    if token not in search and token != 'At most one': fail(f'adaptive search routing missing: {token}')
if 'At most one' not in search and 'one-query rotating recovery probe' not in search: fail('degraded search providers are not limited to recovery exploration')
for token in ('def _source_efficiency_map', 'active_records', 'discarded_records', 'retention_rate', 'high-error request flood'):
    if token not in fresh: fail(f'adaptive direct-source routing missing: {token}')
if 'provider_query_allowance(provider,cfg.queries_per_provider)' not in discovery: fail('campaign search does not apply adaptive provider query allowance')
if 'provider_query_allowance(provider,base_queries_per_provider)' not in cold: fail('Hidden Leads does not apply adaptive provider query allowance')

# Cloud empty-output bug / failover behavior.
for token in ('_manual_empty_retry_minimal', '_manual_disable_json_mime', 'empty_output_retry_mode'):
    if token not in ai: fail(f'Gemini empty-output recovery missing: {token}')
if 'scoutbox_accounted' not in ai: fail('Gemini empty-output token accounting protection missing')

# Downstream quality fixes identified from the one-week assessment.
if 'def _hidden_lead_organization_signal' not in cold or "'weak_organization'" not in cold: fail('Hidden Lead first-party organization gate missing')
for token in ("'marketing'", "'campaigns'", "'recruit'", "'recruiter'", "'work'", "'askhr'", "'peopleops'"):
    if token not in mailbox: fail(f'functional Address Book mailbox classification missing: {token}')
if 'repair_functional_contact_flags' not in migration or 'generic=True' not in migration: fail('existing functional Address Book contacts are not repaired')

# Runtime regression coverage is shipped even when the release verifier host lacks Django.
for token in (
    'test_productive_provider_keeps_query_slice_and_degraded_provider_gets_probe',
    'test_recycled_provider_is_demoted_to_recovery_probe',
    'test_forum_local_ai_yields_when_primary_discovery_is_waiting',
    'test_forum_cloud_rate_limit_does_not_sleep_through_backoff',
    'test_forum_local_ai_yields_to_any_background_job',
    'test_forum_cloud_web_empty_output_does_not_retry_or_failover',
    'test_low_yield_retained_engine_gets_diversification_slice_not_full_volume',
    'test_cloud_web_retries_gemini_empty_output_with_minimal_mode',
    'test_generic_repair_migration_marks_existing_functional_contacts_without_deleting',
    'test_hidden_lead_requires_first_party_organization_evidence',
):
    if token not in tests: fail(f'0.10.79 runtime regression missing: {token}')

print('ScoutBox 0.10.79 targeted regressions passed.')
