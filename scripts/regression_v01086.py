#!/usr/bin/env python3
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text()

def fail(message):
    raise SystemExit(f'FAIL: {message}')

if read('VERSION').strip() != '0.10.86':
    fail('VERSION is not 0.10.86')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.86':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.86':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.86'):
    fail('README not bumped')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.86.md').is_file():
    fail('0.10.86 release notes missing')
if not (ROOT / 'portal' / 'migrations' / '0112_v01086_blacklist_aggregator_recovery.py').is_file():
    fail('0.10.86 aggregator blacklist recovery migration missing')

models = read('portal/models.py')
settings = read('templates/portal/settings.html')
tasks = read('portal/tasks.py')
views = read('portal/views.py')
base = read('templates/portal/base.html')
css = read('portal/static/portal/app.css')
blacklist = read('portal/services/blacklist.py')
blacklist_tpl = read('templates/portal/blacklist.html')
opps_tpl = read('templates/portal/opportunities.html')
contacts_tpl = read('templates/portal/contacts.html')
compose = read('docker-compose.yml')

def require(text, token, label):
    if token not in text:
        fail(f'missing {label}: {token}')

for token in ('MAX_CONCURRENT_CAMPAIGNS_DEFAULT = 5', 'MAX_CONCURRENT_CAMPAIGNS_LIMITS = (2, 10)', 'max_concurrent_campaigns = models.PositiveSmallIntegerField'):
    require(models, token, 'max concurrent model setting')
for token in ('name="max_concurrent_campaigns"', 'min="2"', 'max="10"', 'primary campaign runs · 2–10'):
    require(settings, token, 'settings UI max concurrent campaign control')
for token in ('max_concurrent_campaigns', 'return max(2, min(10, number))'):
    require(tasks.replace(' ', ''), token.replace(' ', ''), 'scheduler max concurrent campaign wiring')
require(compose, '--concurrency=5', 'discovery worker default concurrency')

for token in ('LABEL_BLACKLIST_MIN_CHARS = 7', 'normalize_label', 'valid_label_only_pattern', 'is_blacklisted_company', '_label_only_match', 'company is not None'):
    require(blacklist, token, 'domainless blacklist support')
for token in ('Company Name', 'No domain', 'Company-name-only match', 'Minimum {{label_min_chars}} characters when Domain is empty'):
    require(blacklist_tpl, token, 'blacklist template terminology/help')
for token in ('prepareOpportunityBlacklist', 'bulk-blacklist-action', "{% icon 'blacklist' %}"):
    require(opps_tpl, token, 'Opportunity toolbar blacklist action')
for token in ('_upsert_blacklist_rule', '_blacklist_selected_opportunities', 'LABEL_BLACKLIST_MIN_CHARS', 'enforce_active_blacklist'):
    require(views, token, 'blacklist view integration')

for token in ('scoutboxActiveAutoRefreshListKey', 'scoutboxListRefreshIsSafe', 'scoutboxMaybeRefreshVisibleListAfterBadgeUpdate', 'refreshAsyncList(form,window.location.href)', 'contacts-table'):
    require(base, token, 'new item list auto-refresh')
require(contacts_tpl, 'contact-company-link', 'Address Book company email-domain hyperlink')
for token in ('table th.sortable{position:relative!important', 'padding-right:30px!important', 'table th.sortable:after{position:absolute!important', '#opportunity-table .opportunity-highlight-cell'):
    require(css, token, 'sort icon and Opportunity width CSS')

for token in ('Do not queue Company Enrichment behind an entire Local Discovery campaign', 'waiting for whole campaigns caused persistent Company Enrichment stalls', '_clear_local_wait_state(job)'):
    require(tasks, token, 'company enrichment non-stall handling')


ollama = read('portal/services/ollama.py')
ai = read('portal/services/ai.py')
discovery = read('portal/services/discovery.py')
enrichment = read('portal/services/enrichment.py')
company_research = read('portal/services/company_research.py')
env = read('.env.example')
for token in ('stream=True', '_stream_generate', 'Ollama request exceeded', 'streamed_total_timeout'):
    require(ollama, token, 'bounded streaming Ollama request')
for token in ('_clear_stale_local_ai_lanes', 'legacy_lock', 'heartbeat_stale', '_refresh_local_ai_lane', 'stale_lock_reclaimed'):
    require(ai, token, 'stale Local AI lane recovery')
for token in ('except LocalAILaneBusy:\n            raise', 'local_pre_persistence_gate'):
    require(discovery, token, 'Local AI lane busy propagation from discovery gates')
require(enrichment, 'except LocalAILaneBusy:\n        raise', 'Local AI lane busy propagation from enrichment')
for token in ('except LocalAILaneBusy:\n        raise', 'AI summary: {exc}'):
    require(company_research, token, 'Local AI lane busy propagation from company research')
for token in ('SCOUTBOX_CAMPAIGN_STALL_WARN_MINUTES=8', 'SCOUTBOX_CAMPAIGN_STALL_FAIL_MINUTES=20', 'SCOUTBOX_LOCAL_AI_STALE_LOCK_SECONDS=0'):
    require(env, token, 'stale run/lane default environment')
if not (ROOT / 'portal' / 'migrations' / '0111_v01085_stalled_local_ai_recovery.py').is_file():
    fail('0.10.86 stalled Local AI recovery migration missing')


for token in ('AGGREGATOR_BLACKLIST_DOMAINS', 'is_aggregator_blacklist_domain', "scope == 'opportunities'", 'himalayas.app'):
    require(blacklist, token, 'aggregator blacklist protection')
for token in ("_upsert_blacklist_rule('',label,'Added from Opportunities','all')", '_opportunity_blacklist_label', 'Could not determine a Company Name', 'Job-board and aggregator domains cannot be blacklisted'):
    require(views.replace(' ', ''), token.replace(' ', ''), 'Opportunity company-name-only blacklist')
for token in ('opportunity-blacklist-modal', 'opportunity-blacklist-scroll', 'toggleOpportunityBlacklistRows', 'submitOpportunityBlacklistSelection', 'data-blacklist-domain', 'data-blacklist-company'):
    require(opps_tpl, token, 'Opportunity blacklist review dialog')
for token in ('exact_source', "post.get('source')", "acquisition.get('adapter')"):
    require(read('portal/templatetags/portal_extras.py'), token, 'post-age source tooltip fallback')
for token in ('0112_v01086_blacklist_aggregator_recovery', 'Converted from aggregator-domain blacklist', 'Recycled by v0.10.86'):
    require(read('portal/migrations/0112_v01086_blacklist_aggregator_recovery.py'), token, 'automatic aggregator blacklist migration')
for token in ('#opportunity-table th:nth-child(7)', '#contacts-table th:nth-child(6)', 'padding-right:14px'):
    require(css, token, 'timestamp right padding')

# Basic parse catches JavaScript-in-template string quoting issues poorly, but does catch Python regressions.
for path in Path(ROOT / 'portal').rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
for path in Path(ROOT / 'scripts').rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))

print('ScoutBox 0.10.86 targeted regressions passed.')
