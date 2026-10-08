from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def fail(message):
    raise SystemExit(f'FAIL: {message}')


if read('VERSION').strip() != '0.10.82':
    fail('VERSION is not 0.10.82')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.82':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.82':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.82'):
    fail('README not bumped')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.82.md').is_file():
    fail('0.10.82 release notes missing')

queryplanner = read('portal/services/queryplanner.py')
tasks = read('portal/tasks.py')
campaigns_template = read('templates/portal/campaigns.html')
email_history = read('templates/portal/email_history.html')
env = read('.env.example')
tests = read('portal/tests/test_v01082.py')

for token in (
    'def _append_site_constraint_once',
    'seen_site=[False]',
    '_append_site_constraint_once(out, cleaned, seen_site)',
):
    if token not in queryplanner:
        fail(f'single-site query sanitizer missing: {token}')

capacity_fn = tasks[tasks.index('def _local_discovery_capacity_limit'):tasks.index('def _automatic_discovery_inflight_limit')]
if "SCOUTBOX_LOCAL_AI_GENERATION_LANES" in capacity_fn and "must not reduce search/fetch/direct" not in capacity_fn:
    fail('Local campaign capacity still appears tied to generation lanes')
for token in (
    'SCOUTBOX_LOCAL_CAMPAIGN_INFLIGHT',
    '_local_discovery_capacity_limit(discovery_inflight_limit)',
):
    if token not in tasks:
        fail(f'Local campaign concurrency fix missing: {token}')

if '{{c.ui_opportunities}} opportunit' in campaigns_template or '{{c.ui_leads}} lead' in campaigns_template:
    fail('Campaign Status column still displays retained opportunity/lead counts')
if '{{c.ui_status_detail}}' not in campaigns_template:
    fail('Campaign Status column does not display concise active-run timing')
if 'For {elapsed} · since {since}' not in read('portal/views.py'):
    fail('Running campaign timing detail missing')

first_line = email_history.splitlines()[1]
if '<span class="spacer"></span>' in first_line or 'Date range applies to all Email History tabs and exports.</span>' in first_line:
    fail('Email History range toolbar still leaves a trailing spacer/message box')
if 'email-history-range-card' not in email_history:
    fail('Email History range card lacks cleanup class')

if 'SCOUTBOX_LOCAL_CAMPAIGN_INFLIGHT=2' not in env:
    fail('Local campaign inflight env example missing')

for token in (
    'test_search_query_keeps_only_one_site_constraint',
    'test_local_campaign_capacity_is_not_generation_lane_capacity',
    'test_explicit_local_campaign_capacity_override_is_honored',
):
    if token not in tests:
        fail(f'0.10.82 runtime regression missing: {token}')

print('ScoutBox 0.10.82 targeted regressions passed.')
