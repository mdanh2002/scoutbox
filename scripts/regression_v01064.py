#!/usr/bin/env python3
from pathlib import Path
import ast
import re
import sys
import types
import importlib.util

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text()

checks=[]
def check(name, ok):
    checks.append((name, bool(ok)))

check('release metadata',
      read('VERSION').strip() == '0.10.64'
      and read('RELEASE_ID').strip() == 'ScoutBox v0.10.64'
      and read('BUILD_INFO.txt').strip() == 'ScoutBox v0.10.64'
      and read('README.md').startswith('# ScoutBox 0.10.64')
      and Path(ROOT / 'docs/RELEASE_NOTES_0.10.64.md').exists())

extras=read('portal/templatetags/portal_extras.py')
check('role location display filter present',
      'def role_location_display' in extras
      and 'ast.literal_eval' in extras
      and 'raw JSON is never printed' in extras
      and 'return text[:120]' in extras)

opps=read('templates/portal/opportunities.html')
campaign=read('templates/portal/campaign_detail.html')
detail=read('templates/portal/opportunity_detail.html')
check('templates use safe role location display',
      'o.role_location|role_location_display' in opps
      and '{{role_loc|default:company_loc}}' in opps
      and 'o.role_location|role_location_display' in campaign
      and 'opportunity.role_location|role_location_display|default:"Not set"' in detail
      and '{{o.role_location|default:company_loc}}' not in opps + campaign)

content_quality=read('portal/services/content_quality.py')
check('extract role location drops large eligibility arrays',
      'Large JobPosting/applicantLocationRequirements country arrays' in content_quality
      and 'if len(vals) > 3:' in content_quality)

migration=read('portal/migrations/0099_v01054_role_location_json_cleanup.py')
check('role location repair migration exists',
      'repair_location_json_fields' in migration
      and "('portal','Opportunity','role_location')" in migration
      and "('portal','Opportunity','country')" in migration
      and "('portal','CompanyLead','country')" in migration
      and "('portal','Contact','company_country')" in migration)

# Load the migration helpers with a small fake Django module and test the exact
# multi-country JSON pattern that previously leaked into list rows.
migrations=types.SimpleNamespace(Migration=object, RunPython=lambda *a, **k: ('RunPython', a, k))
migrations.RunPython.noop = lambda *a, **k: None
db=types.SimpleNamespace(migrations=migrations)
django=types.SimpleNamespace(db=db)
sys.modules.setdefault('django', django)
sys.modules.setdefault('django.db', db)
sys.modules.setdefault('django.db.migrations', migrations)
spec=importlib.util.spec_from_file_location('mig1054', ROOT / 'portal/migrations/0099_v01054_role_location_json_cleanup.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
leaky='[{"@type":"Country","name":"Antigua and Barbuda"},{"@type":"Country","name":"Bahamas"},{"@type":"Country","name":"Barbados"},{"@type":"Country","name":"Belize"}]'
check('json country array cleaned',
      mod._country_labels(leaky)[:2] == ['Antigua and Barbuda','Bahamas']
      and mod._clean_role_location(leaky) == ''
      and mod._clean_single_country(leaky) == ''
      and mod._clean_role_location('{"@type":"Country","name":"United States"}') == 'United States')


tasks = read('portal/tasks.py')
mailbox = read('portal/services/mailbox.py')
views = read('portal/views.py')
check('campaign ownership watchdog is heartbeat authoritative',
      'running CampaignRun is finalized only by the heartbeat stall timeout' in tasks
      and "'interrupted_ids':[]" in tasks.replace(' ', '')
      and 'Campaign worker ownership unknown' in tasks
      and not re.search(r"reason\s*=\s*f['\"]Campaign worker task is no longer active", tasks))
check('campaign stall timeout conservative',
      "SCOUTBOX_CAMPAIGN_STALL_FAIL_MINUTES','240'" in tasks
      and 'max(180' in tasks
      and 'warned_ids' in tasks)
check('address book fit fallback helper present',
      'def ensure_addressbook_contact_fit' in mailbox
      and 'Address Book deterministic fallback' in mailbox
      and 'Address Book inherited Fit fallback' in mailbox
      and "contact.save(update_fields=['company_intel','updated_at'])" not in mailbox
      and "row.save(update_fields=['company_intel','updated_at'])" not in views)
check('address book fit fallback migration exists',
      Path(ROOT / 'portal/migrations/0100_v01055_campaign_worker_contact_fit.py').exists()
      and 'Address Book deterministic fallback' in read('portal/migrations/0100_v01055_campaign_worker_contact_fit.py'))
check('discovery concurrency is restored with targeted contention controls',
      'SCOUTBOX_DISCOVERY_AUTO_INFLIGHT=2' in read('.env.example')
      and 'SCOUTBOX_LOCAL_AI_GENERATION_LANES=1' in read('.env.example')
      and 'SCOUTBOX_PUBLIC_PROVIDER_MIN_INTERVAL_SECONDS=6' in read('.env.example')
      and 'SCOUTBOX_CAMPAIGN_STALL_FAIL_MINUTES=240' in read('.env.example')
      and '"--queues=discovery", "--concurrency=2"' in read('docker-compose.yml'))

ai = read('portal/services/ai.py')
search = read('portal/services/search.py')
check('local ai lane semaphore present',
      'def _run_ollama_with_campaign_lane' in ai
      and 'scoutbox:local-ai:lane:' in ai
      and 'Waiting for local AI lane' in ai
      and 'fail open' in ai.lower()
      and 'ollama.generate' in ai
      and '_run_ollama_with_campaign_lane(_ollama_call' in ai)
check('provider pacing present',
      'def _wait_for_provider_pacing' in search
      and 'SCOUTBOX_PUBLIC_PROVIDER_MIN_INTERVAL_SECONDS' in search
      and 'search_provider_pacing' in search
      and 'scoutbox:search-provider:last:' in search)


contacts = read('templates/portal/contacts.html')
css = read('portal/static/portal/app.css')
extras = read('portal/templatetags/portal_extras.py')
check('address book company info sort glyph restored',
      '<th data-sortable class="company-info-list-head">Company Info</th>' in contacts
      and 'data-sort="{{c|company_info_sort_value}}"' in contacts
      and 'def company_info_sort_value' in extras
      and 'th.company-info-list-head' in css)

forum_sources = read('portal/services/forum_sources.py')
fresh_sources = read('portal/services/fresh_sources.py')
models = read('portal/models.py')
opps_template = read('templates/portal/opportunities.html')
sources_template = read('templates/portal/sources.html')
check('forum catalog is native-first and conflict-safe',
      "FORUM_SOURCE_TYPE = 'forum'" in forum_sources
      and "FORUM_DIRECT_ADAPTER = 'forum_generic'" in forum_sources
      and 'EXISTING_01058_COMMUNITY_NAMES' in forum_sources
      and "'Reddit'" in forum_sources
      and "'reddit.com'" in forum_sources
      and "'software':'phpbb'" in forum_sources
      and "'software':'discourse'" in forum_sources
      and "'skip_seed':True" in forum_sources
      and 'native_first' in forum_sources)
check('forum direct adapter is wired',
      'def _forum_generic' in fresh_sources
      and 'FORUM_DIRECT_ADAPTER:_forum_generic' in fresh_sources
      and "'_source_category_override': 'forum'" in fresh_sources
      and "'_apply_via': 'forum'" in fresh_sources)
check('forum UI and contact method filter present',
      'source-forums' in sources_template
      and 'save_forum_sources' in views
      and 'Contact Method' in opps_template
      and 'value="forum"> Forum' in opps_template
      and (("('forum', 'Forum')" in models) or ("('forum','Forum')" in models))
      and "'forum':" in extras)
check('forum age/source reporting present',
      ("source_category')=='forum'" in views or "acq['source_category']='forum'" in views)
      and "return 'Forum'" in views
      and 'Forum post date' in read('portal/services/freshness.py')
      and 'thread bumps/last activity are ignored' in read('portal/services/freshness.py'))


search_log_template = read('templates/portal/search_log.html')
base_template = read('templates/portal/base.html')
sources_template = read('templates/portal/sources.html')
css = read('portal/static/portal/app.css')
check('0.10.64 clean forum list and save label',
      'forum-source-grid' in sources_template
      and 'forum-save-button">Save</button>' in sources_template
      and 'Forum source</span>' not in sources_template
      and 'Native search type' not in sources_template
      and '.forum-source-grid' in css
      and '.forum-source-choice' in css)
check('0.10.64 re-evaluation history button is left aligned',
      'section-actions manual-filter-actions' in read('templates/portal/opportunities.html')
      and 'section-actions manual-filter-actions' in read('templates/portal/cold_contact.html')
      and 'section-actions manual-filter-actions' in read('templates/portal/contacts.html')
      and '.manual-filter-actions .manual-filter-history-launch' in css)
check('0.10.64 search activity provider filters',
      'provider-type-filter' in search_log_template
      and 'provider-filter' in search_log_template
      and 'name="provider_type"' in search_log_template
      and 'name="provider"' in search_log_template
      and 'multi-select-filter-search' in search_log_template
      and 'provider-label-with-icon' in search_log_template
      and 'provider_type_options' in read('portal/views.py')
      and 'provider_type_aliases' in read('portal/views.py')
      and 'provider_names_q' in read('portal/views.py')
      and 'toggleProviderChecks' in base_template
      and '.provider-kind-icon' in css)


check('0.10.64 source tab spacing and preferred search engines label',
      'Preferred Search Engines' in sources_template
      and 'Preferred Sources' not in sources_template.split('data-tabs="sources"',1)[1].split('</div>',1)[0]
      and 'preferred-search-hint' in sources_template
      and 'Used for initial searches in Local AI mode.' in sources_template
      and 'Forum sources use native forum search' not in sources_template
      and 'source-tab-body-compact' in sources_template
      and '</section>\n<section id="source-preferred"' not in sources_template
      and '.source-tab-body-compact' in css)
check('0.10.64 provider type dropdown semantics',
      'provider_type_mode' in search_log_template
      and 'toggleProviderTypeChecks(this)' in search_log_template
      and 'data-toggle-all-label' in search_log_template
      and 'Provider types: {{selected_provider_type_label}}' in search_log_template
      and 'Providers: {{selected_provider_label}}' in search_log_template
      and 'provider_type_all' in views
      and 'provider_type_none' in views
      and 'provider_none' in views
      and 'out of {len(provider_type_order)} selected' in views
      and 'markProviderTypeCustom' in base_template
      and 'toggleProviderTypeChecks' in base_template
      and 'toggleProviderChecks' in base_template)

check('0.10.64 forum browse-before-search semantics',
      'def forum_listing_urls' in forum_sources
      and 'default_forum_listing_paths' in forum_sources
      and 'Forum listing browse' in fresh_sources
      and 'Forum broad native search' in fresh_sources
      and 'looking+for+contractor+qemu' in forum_sources
      and 'exact campaign technology combinations' in read('docs/RELEASE_NOTES_0.10.64.md')
      and ".exclude(source_type='forum')" in search
      and 'site:{domain} ("paid help" OR "paid project"' in read('portal/services/discovery.py'))
check('0.10.64 job presence text cleanup',
      'def _job_presence_text_sample' in tasks
      and 'themeOptions' in tasks
      and 'job_detail_url' in tasks
      and '_clean_retained_opportunity_text' in read('portal/services/opportunity_filter.py')
      and 'themeOptions' in read('portal/services/opportunity_filter.py'))
check('0.10.64 forum health markers',
      'def _forum_source_health' in views
      and 'forum_source_health' in views
      and 'forum-source-health' in sources_template
      and 'provider_no_results_v3' in views
      and 'provider_warn_v3' in views
      and 'provider_ok_v3' in views)

check('0.10.64 re-evaluation scope history launch',
      'portal-choice-history' in base_template
      and 'historyModalId' in base_template
      and 'portal-choice-history-launch' in css
      and "'opportunity-filter-history-modal'" in read('templates/portal/opportunities.html')
      and "'hidden-lead-filter-history-modal'" in read('templates/portal/cold_contact.html')
      and "'contact-filter-history-modal'" in read('templates/portal/contacts.html'))


check('0.10.64 provider type counts classify concrete rows',
      '_classified_rows(provider_type_count_qs)' in views
      and 'provider_type_for(provider,category,stage,meta' in views
      and 'base_filtered_by_type=base.filter(pk__in=_pks_for_types(base,provider_types))' in views
      and 'for pk,provider,kind in _classified_rows(provider_type_count_qs)' in views)
check('0.10.64 history buttons close source modal and do not stay depressed',
      "['opportunity-filter-modal','hidden-lead-filter-modal','contact-filter-modal','portal-choice-modal']" in read('templates/portal/opportunities.html')
      and "['opportunity-filter-modal','hidden-lead-filter-modal','contact-filter-modal','portal-choice-modal']" in read('templates/portal/cold_contact.html')
      and "['opportunity-filter-modal','hidden-lead-filter-modal','contact-filter-modal','portal-choice-modal']" in read('templates/portal/contacts.html')
      and 'history.blur()' in base_template
      and '.manual-filter-history-launch:active' in css
      and '.portal-choice-history-launch:active' in css)

failed=[name for name, ok in checks if not ok]
if failed:
    for name in failed:
        print('FAIL:', name)
    raise SystemExit(1)

# v0.10.64: Engagement Preferences hint is muted and shortened near Save Preferences.
scope_template = read('templates/portal/scope.html')
css = read('portal/static/portal/app.css')
assert 'How these preferences are used' not in scope_template
assert 'notice engagement-preferences-hint' not in scope_template
assert 'preference-save-hint' in scope_template
assert scope_template.index('preference-save-hint') < scope_template.index('Save Preferences')
assert 'guide search planning and fit scoring' in scope_template
assert 'not strict filtering' in scope_template
assert '.preference-save-hint' in css

print('ScoutBox 0.10.64 targeted regressions passed.')

