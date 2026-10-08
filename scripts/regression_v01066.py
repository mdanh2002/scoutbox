#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text()

checks=[]
def check(name, ok):
    checks.append((name, bool(ok)))

check('release metadata',
      read('VERSION').strip() == '0.10.66'
      and read('RELEASE_ID').strip() == 'ScoutBox v0.10.66'
      and read('BUILD_INFO.txt').strip() == 'ScoutBox v0.10.66'
      and read('README.md').startswith('# ScoutBox 0.10.66')
      and Path(ROOT / 'docs/RELEASE_NOTES_0.10.66.md').exists())

fresh_sources = read('portal/services/fresh_sources.py')
forum_sources = read('portal/services/forum_sources.py')
discovery = read('portal/services/discovery.py')
tasks = read('portal/tasks.py')
views = read('portal/views.py')
search_log = read('templates/portal/search_log.html')
base = read('templates/portal/base.html')
sources_template = read('templates/portal/sources.html')
css = read('portal/static/portal/app.css')
migration = read('portal/migrations/0102_v01066_forum_unstarve.py')
notes = read('docs/RELEASE_NOTES_0.10.66.md')

check('forum catalog remains conflict-safe and no Reddit seeding',
      "FORUM_SOURCE_TYPE = 'forum'" in forum_sources
      and "FORUM_DIRECT_ADAPTER = 'forum_generic'" in forum_sources
      and 'EXISTING_01058_COMMUNITY_NAMES' in forum_sources
      and "'Reddit'" in forum_sources
      and "'reddit.com'" in forum_sources
      and "'skip_seed':True" in forum_sources)

check('forum browse before search remains enforced',
      'def forum_listing_urls' in forum_sources
      and 'default_forum_listing_paths' in forum_sources
      and 'Forum listing browse' in fresh_sources
      and 'Forum broad native search' in fresh_sources
      and 'overly specific native searches' in fresh_sources)

check('forum rows can be split from ordinary direct source rows',
      'source_type=None, include_forums=True' in fresh_sources
      and 'def forum_source_rows' in fresh_sources
      and "source_type='forum'" in fresh_sources
      and 'def non_forum_direct_source_rows' in fresh_sources
      and "elif not include_forums:" in fresh_sources)

check('campaign runner browses forums as a separate early stage',
      'forum_source_rows' in discovery
      and 'non_forum_direct_source_rows' in discovery
      and "'Browsing forum sources'" in discovery
      and "'forum_discovery':forum_meta" in discovery
      and "'Checking fresh direct sources'" in discovery)

check('cloud direct qualification reserves room for forum candidates',
      'forum_cap=min(len(forum_records)' in discovery
      and 'qualification_records=list(forum_records[:forum_cap])+list(direct_records[:other_cap])' in discovery
      and 'forum_limit=(8 if test else' in discovery)

check('scheduler allows direct/forum discovery without selected search providers',
      'def _enabled_non_search_discovery_sources' in tasks
      and 'DIRECT_ADAPTERS' in tasks
      and 'and not direct_preflight' in tasks
      and 'non_search_direct_sources_available' in tasks)

check('scheduler ignores stale campaign blockers and finalizes them sooner',
      'def _campaign_run_blocks_scheduling' in tasks
      and 'def _active_campaign_blocker' in tasks
      and "SCOUTBOX_CAMPAIGN_STALL_FAIL_MINUTES','75'" in tasks
      and 'max(45, min(1440, fail_raw))' in tasks
      and 'CampaignRun.objects.filter(campaign=campaign,status__in' in tasks)

check('upgrade releases already-stale campaign rows',
      'release_stale_campaign_runs' in migration
      and 'upgrade_stale_campaign_released' in migration
      and 'upgrade_stale_queue_released' in migration
      and 'timedelta(minutes=90)' in migration)

check('forum browsing is tracked in search activity',
      "category='fresh_source_result'" in fresh_sources
      and "'source_category':('forum' if adapter==FORUM_DIRECT_ADAPTER else 'direct')" in fresh_sources
      and "provider_type_order=('search_engine','direct_search','forum')" in views
      and 'Provider types: {{selected_provider_type_label}}' in search_log)

check('provider dropdown search and 3 provider type UI preserved',
      'toggleProviderChecks' in base
      and 'markProviderTypeCustom' in base
      and 'data-multi-select-option-search' in search_log
      and 'Cloud Provider' not in search_log
      and "'cloud_provider':'Cloud Provider'" not in views)

check('forum source health icons preserved',
      'forum-source-health' in sources_template
      and 'provider_no_results_v3' in views
      and 'provider_warn_v3' in views
      and 'provider_ok_v3' in views
      and '.forum-source-choice' in css)

check('release notes describe forum unstarve fix',
      'dedicated bounded discovery stage' in notes
      and 'direct/forum sources are available' in notes
      and 'stale-heartbeat' in notes)

failed=[name for name, ok in checks if not ok]
if failed:
    for name in failed:
        print('FAIL:', name)
    raise SystemExit(1)
print('ScoutBox 0.10.66 targeted regressions passed.')
