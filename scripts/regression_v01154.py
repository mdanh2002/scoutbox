#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.54 independent selectivity controls."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')
def section(text,start,end=None):
    i=text.index(start)
    if end is None: return text[i:]
    j=text.index(end,i+len(start))
    return text[i:j]

assert read('VERSION').strip()=='0.11.54'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.54'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.54'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.54'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.54.md').exists()
assert (ROOT/'portal/migrations/0151_v01154_independent_selectivity.py').exists()

models=read('portal/models.py')
assert "('broad', 'Broad'), ('balanced', 'Balanced'), ('specialist', 'Specialist')" in models
assert "('broad', 'Broad'), ('balanced', 'Balanced'), ('verified', 'Verified')" in models
for field in ('opportunity_selectivity','lead_selectivity','contact_selectivity'):
    assert f'{field} = models.CharField' in models
    assert f"name='{field}'" in read('portal/migrations/0151_v01154_independent_selectivity.py')

settings=read('templates/portal/settings.html')
for anchor in ('settings-general-opportunity-selectivity','settings-general-lead-selectivity','settings-general-contact-selectivity'):
    assert f'id="{anchor}"' in settings
for name in ('opportunity_selectivity','lead_selectivity','contact_selectivity'):
    assert f'name="{name}"' in settings
assert "id.startsWith('settings-general-')" in settings

views=read('portal/views.py')
post=section(views,"elif action=='save_system':", "elif action=='send_test_digest':")
assert "opportunity_selectivity=(request.POST.get('opportunity_selectivity')" in post
assert "lead_selectivity=(request.POST.get('lead_selectivity')" in post
assert "contact_selectivity=(request.POST.get('contact_selectivity')" in post
assert "'selectivity':_diagnostic_scrub(result.get('selectivity') or criteria.get('selectivity')" in views
assert "'selectivity':_diagnostic_scrub(result.get('selectivity') or (run.criteria or {}).get('selectivity')" in views

dash=read('templates/portal/dashboard.html')
for anchor in ('settings-general-opportunity-selectivity','settings-general-lead-selectivity','settings-general-contact-selectivity'):
    assert anchor in dash
assert 'Jobs: ' in dash and 'Leads: ' in dash and 'Contacts: ' in dash
assert dash.index('dashboard-selectivity-links') < dash.index('id="dashboard-search-control"')

policy=read('portal/services/selectivity.py')
assert "'balanced': {'confidence': 65, 'relevance_confidence': 55, 'fit_score': 0" in policy
assert "'specialist': {'confidence': 80, 'relevance_confidence': 75, 'fit_score': 70" in policy
assert "'balanced': {'semantic_delta': 0, 'minibrowser_cutoff': 75" in policy
assert "'specialist': {'semantic_delta': 10, 'minibrowser_cutoff': 85" in policy
assert "'verified': {'minimum_confidence': 80, 'require_verified_person': True" in policy
assert "'broad': {'minimum_confidence': 0" in policy
assert "'embedded','firmware','hardware','linux','iot','security'" in policy
assert 'def specialist_alignment(' in policy and 'def contact_identity_verified(' in policy

tasks=read('portal/tasks.py')
assert "run.criteria.setdefault('selectivity', selectivity_snapshot(settings_row))" in tasks
assert "'selectivity':dict((run.criteria or {}).get('selectivity') or {})" in tasks
assert "'selectivity':dict((run.criteria or {}).get('selectivity') or {})" in tasks

discovery=read('portal/services/discovery.py')
assert "opp_policy=opportunity_thresholds(opp_level)" in discovery
assert "int(local_review.get('confidence') or 0)>=int(opp_policy['confidence'])" in discovery
assert "specialist_alignment(campaign" in discovery
assert "cutoff=int(lead_rules.get('minibrowser_cutoff') or 75)" in discovery

cloud=read('portal/services/cloud_discovery.py')
assert "opp_level=selectivity_current('opportunities')" in cloud
assert "if opp_level=='specialist':" in cloud
assert "cutoff=int(lead_policy(selectivity_current('hidden_leads')).get('minibrowser_cutoff') or 75)" in cloud
assert "specialist_selectivity_missing_campaign_anchor" in cloud

cold=read('portal/services/cold.py')
assert "lead_level=selectivity_current('hidden_leads',settings_row)" in cold
assert "if lead_level=='specialist'" in cold
assert "'lead_selectivity':lead_level" in cold

mailbox=read('portal/services/mailbox.py')
auto=section(mailbox,'def maybe_persist_addressbook_contact(', '\n\ndef ')
assert "contact_level=selectivity_current('address_book')" in auto
assert "contact_rules.get('require_verified_person')" in auto
assert "contact_identity_verified(raw,name,evidence_text,contact_confidence)" in auto
assert "elif not standard_allowed and contact_rules.get('allow_useful_shared')" in auto


views_stats=read('portal/views.py')
map_payload=section(views_stats,'def _statistics_world_map_payload(', '\ndef _apply_focus_filters')
assert "_stats_geo_layer('applications'" not in map_payload
assert "buckets['applications']" not in map_payload
map_async=section(views_stats,'def stats_map_resolve_async(', '\ndef _refresh_hidden_lead_target_status')
assert "'applications'" not in map_async
assert 'Applications/Outreach' not in map_async

notes=read('docs/RELEASE_NOTES_0.11.54.md')
assert 'Opportunity selectivity' in notes and 'Lead selectivity' in notes and 'Contact admission' in notes
assert 'Applications & Outreach is no longer plotted' in notes
assert 'default to **Balanced**' in notes

print('ScoutBox 0.11.54 regression checks passed')
