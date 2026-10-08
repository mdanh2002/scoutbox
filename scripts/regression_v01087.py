#!/usr/bin/env python3
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text()

def fail(message):
    raise SystemExit(f'FAIL: {message}')

if read('VERSION').strip() != '0.10.87':
    fail('VERSION is not 0.10.87')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.87':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.87':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.87'):
    fail('README not bumped')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.87.md').is_file():
    fail('0.10.87 release notes missing')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.86.md').is_file():
    fail('0.10.86 release notes missing')
if not (ROOT / 'portal' / 'migrations' / '0112_v01086_blacklist_aggregator_recovery.py').is_file():
    fail('0.10.86 aggregator blacklist recovery migration missing')
if not (ROOT / 'portal' / 'tests' / 'test_v01087.py').is_file():
    fail('0.10.87 status facet regression test missing')

views = read('portal/views.py')
css = read('portal/static/portal/app.css')
regression = read('portal/tests/test_v01087.py')
ai = read('portal/services/ai.py')

def require(text, token, label):
    if token not in text:
        fail(f'missing {label}: {token}')

require(views, "status_count_base.order_by().values('status').annotate(n=Count('pk',distinct=True))", 'ordering-free status facet aggregation')
require(views, ".order_by().values(field).annotate(n=Count('pk',distinct=True))", 'ordering-free country facet aggregation')
require(views, 'Facet invariant: All statuses must equal the visible status choice counts.', 'status facet invariant')
for token in ('All statuses (6)', 'New (3)', 'Apply Now (2)', 'Review (1)', 'opportunity.campaigns.add(campaign, rediscovery)'):
    require(regression, token, 'status count regression coverage')
require(ai, "'scoutbox_version': '0.10.87'", 'AI telemetry version stamp')
require(css, 'ScoutBox 0.10.87', 'CSS release marker')

# Keep the v0.10.86 fixes present while adding the v0.10.87 facet fix.
blacklist = read('portal/services/blacklist.py')
opps_tpl = read('templates/portal/opportunities.html')
for token in ('AGGREGATOR_BLACKLIST_DOMAINS', 'is_aggregator_blacklist_domain', 'himalayas.app'):
    require(blacklist, token, 'aggregator blacklist protection')
for token in ('opportunity-blacklist-modal', 'opportunity-blacklist-scroll', 'toggleOpportunityBlacklistRows', 'submitOpportunityBlacklistSelection', 'data-blacklist-domain', 'data-blacklist-company'):
    require(opps_tpl, token, 'Opportunity blacklist review dialog')

for path in Path(ROOT / 'portal').rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
for path in Path(ROOT / 'scripts').rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))

print('ScoutBox 0.10.87 targeted regressions passed.')
