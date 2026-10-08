#!/usr/bin/env python3
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]
def t(p): return (R/p).read_text()
def req(s,x,label=''):
    if x not in s: raise SystemExit('FAIL missing '+(label or x))
assert t('VERSION').strip()=='0.10.93'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.93'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.93'

views=t('portal/views.py')
req(views,'def _show_deleted_setting(request, list_key):','session Show Deleted helper')
for key in ('campaigns','opportunities','applications','contacts','hidden_leads','blacklist'):
    req(views,f"_show_deleted_setting(request,'{key}')",f'Show Deleted session state: {key}')
base=t('templates/portal/base.html')
req(base,"u.searchParams.set('show_deleted',active?'0':'1')",'explicit Show Deleted state toggle')

cold=t('portal/services/cold.py')
for token,label in (
    ('def _hidden_page_is_job_like','vacancy page detection without Careers-nav false positives'),
    ('def _corroborate_hidden_lead_organization','same-domain company corroboration'),
    ('def _resolve_editorial_hidden_lead','publisher-to-company resolution'),
    ('def _salvage_rejected_opportunities','rejected Opportunity salvage'),
    ("'provenance_type':provenance",'rich Hidden Lead scoring provenance'),
    ("'type':'salvaged_opportunity'",'salvaged provenance state'),
    ("'type':'discovered_company'",'discovered provenance state'),
    ("'structural_blocker_penalty'",'structural blocker penalty'),
    ("timestamp()//1800",'rotating Hidden Lead query window'),
    ("'software defined radio'",'SDR discovery family'),
    ("'emulator'",'emulator discovery family'),
    ("'VoIP'",'VoIP discovery family'),
    ("'opportunity_salvage':salvage",'salvage scan result'),
    ("'represented_by_opportunity'",'active Opportunity overlap visibility'),
): req(cold,token,label)
req(cold,"for pass_index in range(len(patterns)):",'one-query-per-rotated-term planning')
req(cold,"candidate_is_platform and retained_org",'company domain not mandatory with retained evidence')

req(cold,'def _retained_company_corroboration','retained Opportunity/Lead/Address Book company corroboration')
req(cold,"corroboration_cap=(16 if discovery_mode=='cloud_web' else 12)",'bounded per-scan company corroboration')
req(cold,"'corroboration_budget_exhausted'",'corroboration budget diagnostics')
company_research=t('portal/services/company_research.py')
req(company_research,'from portal.models import Opportunity, CompanyLead, Contact','Address Book included in retained company context')
req(company_research,'Contact.objects.filter(cq,deleted_at__isnull=True)','active Address Book retained context')

cloud=t('portal/services/cloud_discovery.py')
req(cloud,"'type':'discovered_company'",'Cloud Hidden Lead provenance')

mail=t('portal/services/mailbox.py')
req(mail,'def _company_focused_summary_from_record','Address Book company summary recovery')
req(mail,'summary=_company_focused_summary_from_record(record,values)','Address Book promotion summary use')
migration=t('portal/migrations/0116_v01093_addressbook_summary_backfill.py')
req(migration,"Contact.objects.filter(company_summary='')",'blank Address Book summary backfill')

fresh=t('portal/services/fresh_sources.py')
req(fresh,'def _forum_source_cooldown','Forum broken-source cooldown')
req(fresh,"timestamp()//900",'15-minute Forum rotation')
req(fresh,'effective_sources=min(3,requested_sources)','Forum source failover cap')
req(fresh,"if str(source_type or '').lower()=='forum' and not err",'Forum successful-source stop')
disc=t('portal/services/discovery.py')
req(disc,"SCOUTBOX_FORUM_FAILOVER_SOURCES_PER_PASS','3'",'legacy-safe Forum failover setting')
env=t('.env.example')
req(env,'SCOUTBOX_FORUM_FAILOVER_SOURCES_PER_PASS=3','Forum failover env default')

lead_template=t('templates/portal/cold_contact.html')
req(lead_template,'From unsuitable opportunity','Hidden Lead salvage provenance display')
req(lead_template,'latest_scan_job.result.opportunity_salvage','Hidden Lead salvage scan detail')
req(lead_template,'latest_scan_job.result.filtered.items','Hidden Lead rejection funnel detail')
css=t('portal/static/portal/app.css')
req(css,'.lead-provenance-note','Hidden Lead provenance styling')
req(css,'.hidden-lead-scan-funnel','Hidden Lead scan funnel styling')
extras=t('portal/templatetags/portal_extras.py')
req(extras,'def labelize(value):','scan diagnostic label formatting')

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.93 targeted regressions passed.')
