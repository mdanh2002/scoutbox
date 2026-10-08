from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text()

def fail(message):
    raise SystemExit(f'FAIL: {message}')

if read('VERSION').strip() != '0.10.80': fail('VERSION is not 0.10.80')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.80': fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.80': fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.80'): fail('README not bumped')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.80.md').is_file(): fail('0.10.80 release notes missing')

tasks = read('portal/tasks.py')
fresh = read('portal/services/fresh_sources.py')
search = read('portal/services/search.py')
discovery = read('portal/services/discovery.py')
compose = read('docker-compose.yml')
env = read('.env.example')
tests = read('portal/tests/test_v01080.py')

# Dedicated queue remains, but scheduling must now require deep primary idle rather than
# merely an empty worker slot at one scheduler tick.
for token in ('forum_worker:', '--queues=forum', '--concurrency=1'):
    if token not in compose: fail(f'Forum queue isolation missing: {token}')
for token in ('def _forum_primary_idle_state', 'primary search coverage incomplete', 'Cloud primary discovery is due soon', 'forum_idle_ok'):
    if token not in tasks: fail(f'deep-idle Forum priority guard missing: {token}')
if "primary_inflight==0 and higher_priority_background_work==0 and forum_idle_ok" not in tasks:
    fail('Forum scheduler can start without deep-idle approval')
if "queue='forum'" not in tasks: fail('Forum jobs are not routed to dedicated queue')

# Forum passes are intentionally tiny and cooperatively preemptible.
for token in (
    "SCOUTBOX_FORUM_ONLY_STAGE_MAX_SECONDS','25'",
    "SCOUTBOX_FORUM_SOURCES_PER_PASS','1'",
):
    if token not in discovery: fail(f'strict Forum campaign bound missing: {token}')
for token in (
    "SCOUTBOX_FORUM_FETCH_TIMEOUT_SECONDS','5'",
    "SCOUTBOX_FORUM_LISTING_URLS_PER_SOURCE','1'",
    "SCOUTBOX_FORUM_NATIVE_SEARCHES_PER_SOURCE','1'",
    'def stop_requested()',
    'should_stop=should_stop',
    'Forum browse yielded to primary discovery.',
    'effective_sources=1',
    'effective_budget=min(hard_budget,requested_budget)',
):
    if token not in fresh: fail(f'Forum HTTP preemption/bound missing: {token}')
for token in (
    'SCOUTBOX_FORUM_BROWSE_INTERVAL_MINUTES=360',
    'SCOUTBOX_FORUM_GLOBAL_INTERVAL_MINUTES=120',
    'SCOUTBOX_FORUM_PRIMARY_GUARD_MINUTES=5',
    'SCOUTBOX_FORUM_ONLY_STAGE_MAX_SECONDS=25',
    'SCOUTBOX_FORUM_SOURCES_PER_PASS=1',
):
    if token not in env: fail(f'Forum safe default missing from .env.example: {token}')

# Search balancing keeps productive engines primary and turns known-bad exploration into
# a global, slow recovery probe rather than one probe per concurrent campaign.
for token in ('def _degraded_provider_probe_due', 'SCOUTBOX_DEGRADED_SEARCH_PROBE_INTERVAL_MINUTES', 'due_recovery'):
    if token not in search: fail(f'degraded-provider global probe cooldown missing: {token}')
if 'provider_query_allowance(provider,cfg.queries_per_provider)' not in discovery:
    fail('primary search no longer applies adaptive per-provider allowance')
if 'SCOUTBOX_DEGRADED_SEARCH_PROBE_INTERVAL_MINUTES=240' not in env:
    fail('degraded search probe default missing')

for token in (
    'test_local_forum_waits_until_primary_search_coverage_is_complete',
    'test_cloud_forum_does_not_start_when_primary_cloud_run_is_due_soon',
    'test_forum_adapter_preempts_before_first_http_request',
    'test_recent_degraded_probe_blocks_duplicate_campaign_probe',
):
    if token not in tests: fail(f'0.10.80 runtime regression missing: {token}')

print('ScoutBox 0.10.80 targeted regressions passed.')
