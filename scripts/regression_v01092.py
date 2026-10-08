#!/usr/bin/env python3
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]
def t(p): return (R/p).read_text()
def req(s,x,label=''):
    if x not in s: raise SystemExit('FAIL missing '+(label or x))
assert t('VERSION').strip()=='0.10.92'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.92'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.92'
d=t('portal/services/discovery.py')
if '_JOB_AGGREGATOR_BRANDS' in d: raise SystemExit('FAIL stale undefined aggregator registry reference remains')
req(d,"brand=registrable_domain(host) or host or 'job-board'",'shared job-board grouping')
tasks=t('portal/tasks.py')
req(tasks,"SCOUTBOX_FORUM_BROWSE_INTERVAL_MINUTES','15'",'15-minute forum campaign cadence')
req(tasks,"SCOUTBOX_FORUM_GLOBAL_INTERVAL_MINUTES','15'",'15-minute forum global cadence')
req(tasks,'forum_launch_allowed=True','forum acquisition not deep-idle gated')
req(tasks,"known_release_bug='_JOB_AGGREGATOR_BRANDS'",'0.10.91 failure circuit-breaker bypass')
fresh=t('portal/services/fresh_sources.py')
req(fresh,'timestamp()//900','15-minute forum source rotation')
env=t('.env.example')
req(env,'SCOUTBOX_FORUM_BROWSE_INTERVAL_MINUTES=15')
req(env,'SCOUTBOX_FORUM_GLOBAL_INTERVAL_MINUTES=15')
for fn, token in {
    'opportunities.html':'{% if o.user_deleted %}disabled title="Restore this item before selecting it"{% endif %}',
    'cold_contact.html':'{% if x.user_deleted %}disabled title="Restore this item before selecting it"{% endif %}',
    'applications.html':'{% if a.deleted_at %}disabled title="Restore this item before selecting it"{% endif %}',
    'contacts.html':'{% if c.deleted_at %}disabled title="Restore this item before selecting it"{% endif %}',
    'blacklist.html':'{% if x.deleted_at %}disabled title="Restore this item before selecting it"{% endif %}',
    'campaigns.html':'{% if c.deleted_at %}disabled title="Restore this item before selecting it"',
}.items(): req(t('templates/portal/'+fn),token,fn+' deleted checkbox safety')
opp=t('templates/portal/opportunities.html')
req(opp,".filter(x=>!x.disabled)",'Opportunity selected rows ignore disabled')
lead=t('templates/portal/cold_contact.html'); req(lead,".filter(x=>!x.disabled)",'Hidden Lead selected rows ignore disabled')
contacts=t('templates/portal/contacts.html'); req(contacts,".filter(x=>!x.disabled)",'Address Book selected rows ignore disabled')
req(opp,'Internet Search verifies the listing and refreshes company, contact, remote and post-age data.')
req(opp,'~1 AI request/item.')
req(opp,'Only company names are blacklisted. Verified company domains are shown for reference; job boards, ATS hosts and aggregators are excluded.')
css=t('portal/static/portal/app.css'); req(css,'.manual-filter-web-help,.manual-filter-secondary-help{font-size:11px;line-height:1.35}')
req(css,'.opportunity-blacklist-help{font-size:11px;line-height:1.35')
views=t('portal/views.py')
for token in ['Opportunity.objects.filter(suppressed=False,user_deleted=False)','CompanyLead.objects.filter(user_deleted=False)','Contact.objects.filter(deleted_at__isnull=True)']:
    req(views,token,'server-side active-only filtering')
for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.92 targeted regressions passed.')
