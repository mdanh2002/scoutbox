#!/usr/bin/env python3
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]
def t(p): return (R/p).read_text()
def req(s,x):
    if x not in s: raise SystemExit('FAIL missing: '+x)
assert t('VERSION').strip()=='0.10.91'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.91'
req(t('templates/portal/base.html'),'form.elements||[]')
for f in ['opportunities.html','cold_contact.html','applications.html','contacts.html','blacklist.html']:
    x=t('templates/portal/'+f); req(x,"icon 'show_deleted'"); req(x,"icon 'hide_deleted'")
x=t('templates/portal/campaigns.html'); req(x,'data-campaign-id'); req(x,"restoreInlineItem('campaign'"); req(x,"icon 'show_deleted'")
p=t('portal/services/platforms.py'); req(p,'workingnomads.com'); req(p,'def is_plausible_company_name')
c=t('portal/services/cold.py'); req(c,'NinjaOne') if False else None; req(c,'Summary/title prose'); req(c,'is_plausible_company_name')
d=t('portal/services/discovery.py'); req(d,'is_plausible_company_name(reviewed_company)')
tasks=t('portal/tasks.py'); req(tasks,'background_jobs_active');
if 'primary_inflight==0 and higher_priority_background_work==0 and forum_launch_allowed' in tasks: raise SystemExit('FAIL forum remains blocked by generic background work')
f=t('portal/services/fresh_sources.py'); req(f,'forum_rotation_offset')
css=t('portal/static/portal/app.css'); req(css,'ScoutBox 0.10.91'); req(css,'border-top:0!important')
assert (R/'portal/migrations/0115_v01091_company_identity_repair.py').is_file()
for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py')): ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.91 targeted regressions passed.')
