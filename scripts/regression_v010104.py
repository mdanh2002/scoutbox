#!/usr/bin/env python3
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.104'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.104'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.104'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.104'

models=t('portal/models.py')
req(models,'country_repair_version = models.CharField','country repair completion marker')
mig=t('portal/migrations/0123_v010103_country_location_repair.py')
req(mig,"name='country_repair_version'",'country repair migration')
forbid(mig,'requests.','migration must not call network')

location=t('portal/services/location.py')
req(location,'resolve_opportunity_location','grounded location resolver')
req(location,"'structured_jobposting'",'structured role-location priority')
req(location,"'direct_source_location'",'direct role-location provenance')
req(location,"fallback=True",'remote company HQ fallback')
req(location,'repopulate_country_fields','upgrade country repair')
req(location,'legacy_country_is_untrusted','legacy AI country cleanup')
forbid(location,'operating_locations','candidate geography excluded from location service')

discovery=t('portal/services/discovery.py')
req(discovery,'resolve_opportunity_location','discovery uses grounded location resolver')
forbid(discovery,"'operating_locations':list(profile.operating_locations",'candidate location removed from discovery AI context')
req(discovery,"facts['country_provenance']",'country provenance persisted')

op_filter=t('portal/services/opportunity_filter.py')
forbid(op_filter,"'operating_locations': profile.operating_locations",'candidate location removed from manual filter context')

tasks=t('portal/tasks.py')
req(tasks,'country_location_repair_job','one-time country repair task')
req(tasks,"ps.country_repair_version='0.10.103'",'country repair completion version retained')
req(tasks,'_queue_country_location_repair(s)','scheduler queues repair')
req(tasks,'Never overwrite','company research must not overwrite role country')

views=t('portal/views.py')
req(views,'country_total=country_count_base.count()','Opportunity All countries full universe')
req(views,'country_total=len(country_visible_ids)','Hidden Lead All countries full universe')
req(views,"'added_asc':('created_at','pk'), 'added_desc':('-created_at','-pk')",'Blacklist full-query Date Added sorting')
req(views,"sort_mode='deleted_desc'",'Recycle Bin full-result sorting')
req(views,"'role_asc','role_desc'",'Opportunity full-result header sorting')
req(views,"'company_asc','company_desc'",'Hidden Lead full-result header sorting')

for name in ('templates/portal/opportunities.html','templates/portal/cold_contact.html','templates/portal/blacklist.html','templates/portal/recycle_bin.html'):
    text=t(name)
    forbid(text,'data-sort-table','server-paginated list must not use current-page client sorter: '+name)
    req(text,'server_sort_url','server sort links: '+name)

opp=t('templates/portal/opportunities.html')
req(opp,"age != 'Age unknown' and o.freshness_confidence",'unknown Opportunity Post Age has no tooltip')
css=t('portal/static/portal/app.css')
req(css,'.summary-url-health{margin-left:4px!important;padding:0 3px!important;font-size:8px!important','compact Opportunity/Lead HTTP badge')
settings=t('templates/portal/settings.html')
forbid(settings,'primary campaign runs · 2–10','obsolete concurrent campaign helper hidden')
req(settings,'min="2" max="10" name="max_concurrent_campaigns"','concurrency range retained')
campaign=t('templates/portal/campaign_detail.html')
req(campaign,"age != 'Age unknown' and o.freshness_confidence",'unknown Campaign Post Age has no tooltip')

research=t('portal/services/company_research.py')
req(research,'https://data.iana.org/rdap/dns.json','IANA RDAP bootstrap')
req(research,'_rdap_registration_event','creation-event-only domain age')
req(research,"'domain_age_unavailable_reason'",'authoritative unavailable state')
req(research,"'domain_age_source'",'RDAP source diagnostics')
req(research,"'domain_age_endpoint'",'RDAP endpoint diagnostics')
forbid(research,"requests.get('https://rdap.org/domain/'+domain",'old single-aggregator domain lookup removed')

# 0.10.104 Focus lifecycle and upgrade repair.
models=t('portal/models.py')
req(models,'focus_taxonomy_state = models.JSONField','Focus taxonomy baselines')
req(models,'integrity_repair_version = models.CharField','integrity repair completion marker')
mig104=t('portal/migrations/0124_v010104_focus_integrity.py')
req(mig104,'adopt_existing_focus_taxonomy','adopt existing Focus taxonomy')
forbid(mig104,'requests.','Focus migration must not call network')
focus=t('portal/services/focus.py')
req(focus,'def focus_taxonomy_rebuild_due','rare Focus rebuild threshold decision')
req(focus,"threshold=max(25,int(math.ceil(baseline*0.25)))",'established corpus 25 percent growth trigger')
req(focus,"(now-last).days>=30 and growth>=10",'monthly rebuild requires meaningful growth')
req(focus,'_build_model_focus_shadow','shadow Focus mapping')
req(focus,'with transaction.atomic():','atomic Focus replacement')
req(focus,"return ''",'unavailable classifier leaves retryable blank Focus')
focus_signals=t('portal/focus_signals.py')
req(focus_signals,"if not created and str(getattr(instance,'focus','') or '').strip():",'only blank Focus retries on later saves')
tasks=t('portal/tasks.py')
req(tasks,"label='Refresh Focus taxonomy'",'stable Focus refresh job')
req(tasks,'focus_taxonomy_rebuild_due(settings_row)','threshold-driven Focus rebuild')
forbid(tasks,'rebalance_focus_taxonomies_once(', 'daily Focus churn removed')
req(tasks,'v010104_integrity_repair_job','one-time integrity repair task')
req(tasks,"ps.integrity_repair_version='0.10.104'",'integrity repair version')

# Blacklist identity is rechecked after persistence/background identity changes.
blacklist=t('portal/services/blacklist.py')
req(blacklist,'BLACKLIST_LEGAL_SUFFIXES','conservative legal-suffix normalization')
req(blacklist,'normalize_company_blacklist_key','canonical company blacklist key')
req(blacklist,'def enforce_active_blacklist','retained blacklist enforcement')
signals=t('portal/blacklist_signals.py')
req(signals,'opportunity_blacklist_invariant','Opportunity blacklist persistence invariant')
req(signals,'lead_blacklist_invariant','Hidden Lead blacklist persistence invariant')
req(t('portal/apps.py'),'from . import blacklist_signals','blacklist signals loaded')

# Wrong-role replacement and generic job-board shells are non-opportunities.
discovery=t('portal/services/discovery.py')
req(discovery,'_replacement_role_page_valid','replacement page independent validation')
req(discovery,'employer_role_replacement_rejected','failed employer replacement audit trail')
req(discovery,'Remote work eligibility could not be confirmed from role-level evidence.','unknown remote rows suppressed')
req(discovery,"(remote_text if result.get('_direct_source') else '')",'search remote text cannot create deterministic remote status')
role_gate=t('portal/services/role_gate.py')
req(role_gate,'Job-board collection/search title rejected','Indeed/JobStreet collection title gate')
req(role_gate,'Application-questionnaire shell rejected','questionnaire shell gate')
req(role_gate,'has_concrete_vacancy_copy','real JD guard for shell rejection')
platforms=t('portal/services/platforms.py')
req(platforms,"'customer service'",'generic employer navigation label rejected')
quality=t('portal/services/content_quality.py')
req(quality,'def remote_work_evidence','role-level remote evidence parser')
req(quality,'def work_arrangement_evidence','grounded Remote/Hybrid/On-site evidence parser')
req(quality,'growing your career','semantic non-evidence documented')
req(quality,"'status':'hybrid'",'explicit Hybrid classification only')
req(quality,'technical/system context, not as a working arrangement','technical remote context rejection')
integrity=t('portal/services/integrity_repair.py')
req(integrity,'repair_existing_opportunity_integrity','retained opportunity integrity repair')
req(integrity,'restored_original_job_board','valid original board restoration')
req(integrity,'remote-work eligibility is not confirmed','retained restore requires remote evidence')
req(integrity,"'remote_badges_repaired':0",'retained unsupported Remote/Hybrid repair')

# Post age/UI polish.
fresh=t('portal/services/freshness.py')
req(fresh,"return '~ 1 week'",'youngest bucket display')
extras=t('portal/templatetags/portal_extras.py')
req(extras,"lines=[f'Post age: {display_age}']",'Post Age tooltip heading')
req(extras,"lines.append(f'{date_heading}: {date_text}')",'Post Age exact/estimated date')
req(extras,"'email_outgoing'",'distinct contact-via Email icon')
opp=t('templates/portal/opportunities.html')
req(opp,"{% icon 'email_outgoing' %}",'Opportunity contact-via Email glyph')
req(opp,'Hide opportunities whose final role URL','Opportunity Hide failed URLs explanation')
req(t('templates/portal/cold_contact.html'),'Hide Hidden Leads whose target/source URL','Hidden Lead Hide failed URLs explanation')
req(t('templates/portal/contacts.html'),'Hide Address Book entries whose company/source URL','Address Book Hide failed URLs explanation')
css=t('portal/static/portal/app.css')
req(css,'.opportunity-inline-apply .svg-icon{width:16px;height:16px','larger contact-via icon')

# Diagnostic record period uses date-added/first-seen, not maintenance timestamps.
views=t('portal/views.py')
req(views,"Q(first_seen_by_portal__gte=start)",'diagnostic Opportunity first-seen period')
req(views,'lead_qs=lead_qs.filter(created_at__gte=start)','diagnostic Hidden Lead date-added period')
req(views,'contact_qs=contact_qs.filter(created_at__gte=start)','diagnostic Address Book date-added period')
req(views,"application_qs=application_qs.filter(Q(date_added__gte=start)|Q(date_added__isnull=True,created_at__gte=start))",'diagnostic Application date-added period')
req(views,'filters ScoutBox records by date added/first seen, not updated_at','diagnostic export semantics note')

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py'))+list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.104 targeted regressions passed.')
