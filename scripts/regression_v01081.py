from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def fail(message):
    raise SystemExit(f'FAIL: {message}')


if read('VERSION').strip() != '0.10.81':
    fail('VERSION is not 0.10.81')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.81':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.81':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.81'):
    fail('README not bumped')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.81.md').is_file():
    fail('0.10.81 release notes missing')
if not (ROOT / 'portal' / 'migrations' / '0109_v01081_campaign_run_flags.py').is_file():
    fail('0.10.81 CampaignRun flag repair migration missing')


discovery = read('portal/services/discovery.py')
tasks = read('portal/tasks.py')
ai = read('portal/services/ai.py')
views = read('portal/views.py')
tests = read('portal/tests/test_v01081.py')

# compileall/AST parsing does not detect a missing runtime global. Check the exact
# v0.10.80 regression explicitly: discovery uses time.monotonic and imports time.
tree = ast.parse(discovery)
imports_time = any(
    isinstance(node, ast.Import) and any(alias.name == 'time' for alias in node.names)
    for node in tree.body
)
if 'time.monotonic()' not in discovery or not imports_time:
    fail('discovery monotonic clock dependency is not imported')

for token in (
    'def _non_forum_runs(rows):',
    'def _primary_coverage_runs(rows):',
    "'forum_only':False",
    "'deferred_local_ai':False",
    'all_primary_runs=_non_forum_runs(',
    'last_any=all_primary_runs[-1]',
    "'recent campaign failures; retry next window'",
):
    if token not in tasks:
        fail(f'scheduler crash-loop protection missing: {token}')

# Missing JSON keys must never be filtered via a negated key lookup again. The Python
# truth helpers deliberately treat missing forum_only/deferred_local_ai as false.
for path, text in [('portal/tasks.py', tasks), ('portal/services/ai.py', ai)]:
    if '.exclude(criteria__forum_only=True)' in text:
        fail(f'unsafe JSON forum exclusion remains in {path}')
if '.exclude(criteria__deferred_local_ai=True)' in tasks:
    fail('unsafe JSON deferred exclusion remains in scheduler')

for token in (
    "criteria['forum_only']=False",
    "criteria['deferred_local_ai']=False",
    'all_primary=[r for r in CampaignRun.objects.filter(',
):
    if token not in views:
        fail(f'manual/dashboard scheduler metadata fix missing: {token}')

for token in (
    'test_campaign_criteria_writes_scheduler_flags_explicitly',
    'test_legacy_missing_forum_flag_is_still_primary',
    'test_failed_primary_attempts_count_as_window_coverage',
    'test_deferred_primary_is_not_coverage_but_remains_primary_attempt',
):
    if token not in tests:
        fail(f'0.10.81 runtime regression missing: {token}')

print('ScoutBox 0.10.81 targeted regressions passed.')
