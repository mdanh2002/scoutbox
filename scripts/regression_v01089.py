#!/usr/bin/env python3
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text()

def fail(message):
    raise SystemExit(f'FAIL: {message}')

def require(text, token, label):
    if token not in text:
        fail(f'missing {label}: {token}')

if read('VERSION').strip() != '0.10.89':
    fail('VERSION is not 0.10.89')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.89':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.89':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.89'):
    fail('README not bumped')
for name in ('RELEASE_NOTES_0.10.86.md', 'RELEASE_NOTES_0.10.87.md', 'RELEASE_NOTES_0.10.88.md', 'RELEASE_NOTES_0.10.89.md'):
    if not (ROOT / 'docs' / name).is_file():
        fail(f'{name} missing')

views = read('portal/views.py')
blacklist = read('portal/services/blacklist.py')
filters = read('portal/templatetags/portal_extras.py')
opps_tpl = read('templates/portal/opportunities.html')
hidden_tpl = read('templates/portal/cold_contact.html')
blacklist_tpl = read('templates/portal/blacklist.html')
opp_detail = read('templates/portal/opportunity_detail.html')
hidden_detail = read('templates/portal/hidden_lead_detail.html')
css = read('portal/static/portal/app.css')
ai = read('portal/services/ai.py')
search_log = read('templates/portal/search_log.html')

require(ai, "'scoutbox_version': '0.10.89'", 'AI telemetry version stamp')
require(views, "status_count_base.order_by().values('status').annotate(n=Count('pk',distinct=True))", 'ordering-free status facet aggregation')
require(views, ".order_by().values(field).annotate(n=Count('pk',distinct=True))", 'ordering-free country facet aggregation')
require(views, 'if domain and is_aggregator_blacklist_domain(domain):', 'global aggregator-domain blacklist guard')
require(views, 'def _hidden_lead_blacklist_label', 'Hidden Lead company-only blacklist helper')
require(views, "_upsert_blacklist_rule('',label,'Added from Hidden Leads','all')", 'Hidden Lead company-only blacklist submit')

for token in (
    'company_specific_blacklist_review_domain', 'company_specific_blacklist_review_domain_for_record',
    '_walk_company_domain_hints', 'domain_age_domain', 'company_intel', 'extracted_facts',
    'registrable_domain', 'is_company_specific_domain', 'AGGREGATOR_BLACKLIST_DOMAINS',
    'sitepoint.com', 'himalayas.app', 'linkedin.com', 'greenhouse.io', 'lever.co', 'ashbyhq.com',
):
    require(blacklist, token, 'blacklist domain review and aggregator protection')
require(filters, 'def blacklist_review_domain_for_record', 'record-aware blacklist review template filter')

for token in (
    'blacklist_review_domain_for_record', 'Company domain', 'submitOpportunityBlacklistSelection',
    'Only company names will be added to the blacklist', 'domainTd.textContent=reviewDomain;if(!reviewDomain){domainTd.classList.add(\'empty\')}',
):
    require(opps_tpl, token, 'Opportunity blacklist review dialog')
for token in (
    'hidden-lead-blacklist-modal', 'toggleHiddenLeadBlacklistRows', 'submitHiddenLeadBlacklistSelection',
    'blacklist_review_domain_for_record', 'Company domain', 'Only company names will be added to the blacklist',
    'domainTd.textContent=reviewDomain;if(!reviewDomain){domainTd.classList.add(\'empty\')}',
):
    require(hidden_tpl, token, 'Hidden Lead blacklist review dialog')
for forbidden in ('reviewDomain||\'—\'', 'Job-board, ATS, aggregator, or non-company domain hidden.'):
    if forbidden in opps_tpl or forbidden in hidden_tpl:
        fail(f'blacklist modal still has empty-domain hint/placeholder: {forbidden}')
for forbidden in ('Company-name-only match', '>No domain</span>'):
    if forbidden in blacklist_tpl:
        fail(f'Blacklist page still shows hidden hint: {forbidden}')
if 'value="blacklist"' in opp_detail:
    fail('Opportunity detail still exposes a Blacklist submitter')
if 'value="blacklist"' in hidden_detail:
    fail('Hidden Lead detail still exposes a Blacklist submitter')
if 'Open Lead' in hidden_detail:
    fail('Hidden Lead detail still exposes Open Lead button')

require(css, 'ScoutBox 0.10.89', 'CSS release marker')
for token in ('-webkit-line-clamp:2!important', '.search-log-table th:nth-child(3)', 'min-width:260px!important', 'table-layout:fixed!important'):
    require(css, token, 'Search Activity query wrapping CSS')
require(search_log, '>Results</a></th>', 'Search Activity Results header')
if not (ROOT / 'portal' / 'migrations' / '0113_v01088_blacklist_domain_recovery.py').is_file():
    fail('0.10.88 aggregator blacklist recovery migration missing')

for path in Path(ROOT / 'portal').rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
for path in Path(ROOT / 'scripts').rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))

print('ScoutBox 0.10.89 targeted regressions passed.')
