from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.116'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.116'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.116'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.116'
assert (root / 'docs/RELEASE_NOTES_0.11.116.md').exists()

views = read('portal/views.py')
for token in (
    "'format_version':5",
    "facebook_page_qs=FacebookPage.objects.all()",
    "tracking_link_qs=TrackingLink.objects.select_related('rule','application__opportunity').all()",
    "'facebook_pages':[serialize_facebook_page(x) for x in facebook_pages]",
    "'tracking_links':[serialize_tracking_link(x) for x in tracking_links]",
    "'facebook_pages':[row.pk for row in facebook_pages if row.deleted_at]",
    "'tracking_links':[row.pk for row in tracking_links if row.deleted_at]",
    "'facebook_pages':len(facebook_pages)",
    "'tracking_links':len(tracking_links)",
    "'facebook_pages','tracking_links','import_history'",
):
    assert token in views, token

selectivity = read('portal/services/selectivity.py')
assert "'balanced': {'semantic_delta': 0, 'minibrowser_cutoff': 75" in selectivity
assert "'outreach_signal_min': 3" in selectivity
assert "'automatic_scan_new_cap': 7" in selectivity

cold = read('portal/services/cold.py')
for token in (
    'def _hidden_lead_outreach_signal(',
    "'weak_outreach_signal':0",
    "market_plan(settings_row,campaign_id=0,rotation_offset=offset)",
    'multilingual_assignments(settings_row,markets,rotation_offset=offset)',
    'def _translate_hidden_market_query(',
    'def _translate_hidden_market_page(',
    "usage_category='hidden_market',market=market",
    "category='discovery_market'",
    "int(outreach.get('score') or 0) < int(lead_rules.get('outreach_signal_min') or 3)",
    "automatic_new_cap=max(1,int(lead_rules.get('automatic_scan_new_cap') or 7))",
    "'multilingual_strength':str(getattr(settings_row,'multilingual_exploration_strength','balanced') or 'balanced')",
):
    assert token in cold, token
assert 'Topical relevance alone is not enough. Require a current practical outreach signal' in cold

search = read('portal/services/search.py')
assert "SCOUTBOX_DEGRADED_SEARCH_PROBE_INTERVAL_MINUTES','360'" in search
assert 'recent=provider_recent_health(source,days=2)' in search
assert 'recent_requests>=24 and recent_unique==0 and recent_active==0' in search
assert "FacebookPage.objects.filter(page_id__iexact=candidate)" in search
assert "row.deleted_at is None and not row.enabled" in search

discovery = read('portal/services/discovery.py')
assert "SCOUTBOX_PROVIDER_QUERY_HARD_CAP','12'" in discovery
assert 'provider_query_allowance(provider,configured_provider_cap)' in discovery

fresh = read('portal/services/fresh_sources.py')
for token in (
    "_INCREMENTAL_ATS_ADAPTERS={'greenhouse','lever','ashby','smartrecruiters'}",
    'def _remove_known_opportunity_urls(rows):',
    'known_opportunity_urls_skipped_by_source',
    "if adapter in _INCREMENTAL_ATS_ADAPTERS:",
):
    assert token in fresh, token

for source in (views, cold, search, discovery, fresh, selectivity):
    ast.parse(source)

mig = read('portal/migrations/0188_v011116_discovery_quality_export.py')
assert "version='0.11.116'" in mig
assert '0187_v011115_concise_search_queries' in mig
print('ScoutBox 0.11.116 targeted regression checks passed')
