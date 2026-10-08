#!/usr/bin/env python3
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.103'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.103'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.103'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.103'

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
req(tasks,"ps.country_repair_version='0.10.103'",'repair completion version')
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

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py'))+list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.103 targeted regressions passed.')
