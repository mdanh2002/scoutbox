#!/usr/bin/env python3
from pathlib import Path
import ast

R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.101'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.101'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.101'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.101'

models=t('portal/models.py')
req(models,'focus_comparison_records = models.PositiveSmallIntegerField(default=100','Focus comparison default')
req(models,'max_focus_groups = models.PositiveSmallIntegerField(default=15','Focus-group default')
if models.count("focus = models.CharField(max_length=80") < 3:
    raise SystemExit('FAIL missing Focus fields on all three list models')

focus=t('portal/services/focus.py')
req(focus,'def _comparison_budget(', 'bounded comparison budget')
req(focus,'pct=0.80 +', 'lower tolerance')
req(focus,'_soft_group_cap', 'focus group tolerance')
req(focus,'*1.20', 'upper group tolerance')
req(focus,'record.__class__.objects.exclude', 'same-list comparison source')
req(focus,'campaign_hint', 'campaign used as hint only')
forbid(focus,'cloud_ai', 'Focus must not invoke Cloud AI')
forbid(focus,'requests.', 'Focus must not invoke network requests')

migration=t('portal/migrations/0121_v010101_focus_facets.py')
req(migration,'def backfill_all_existing_focus(', 'one-time full Focus backfill')
req(migration,'Opportunity.objects.all().iterator(chunk_size=500)', 'full Opportunity backfill')
req(migration,'CompanyLead.objects.all().iterator(chunk_size=500)', 'full Hidden Lead backfill')
req(migration,'Contact.objects.all().iterator(chunk_size=500)', 'full Address Book backfill')
req(migration,'without the runtime sample limit', 'unrestricted one-time backfill contract')
forbid(migration,'_comparison_budget(', 'migration must not apply runtime Focus comparison limit')
forbid(migration,'requests.', 'migration must not use network')

settings=t('templates/portal/settings.html')
req(settings,'name="focus_comparison_records"', 'General Focus comparison setting')
req(settings,'value="{{portal_settings.focus_comparison_records|default:100}}"', 'Focus comparison UI default')
req(settings,'name="max_focus_groups"', 'General max Focus setting')
req(settings,'value="{{portal_settings.max_focus_groups|default:15}}"', 'max Focus UI default')

views=t('portal/views.py')
req(views,"ps.focus_comparison_records=max(25,min(500", 'Focus comparison clamp')
req(views,"ps.max_focus_groups=max(5,min(30", 'Focus group clamp')
req(views,"focus_filter=(request.GET.get('focus') or '').strip()", 'Focus facet query handling')
req(views,"'Focus'", 'Focus export column')

opp=t('templates/portal/opportunities.html')
req(opp,'name="focus"', 'Opportunity Focus facet')
forbid(opp,'name="status"', 'Opportunity Status facet removed')
forbid(opp,'All statuses', 'Opportunity status label removed')
req(opp,'toolbar-actions-right', 'Opportunity actions right aligned')
req(opp,'focus-list-search', 'Opportunity search shortened')

leads=t('templates/portal/cold_contact.html')
req(leads,'name="focus"', 'Hidden Lead Focus facet')
req(leads,'toolbar-actions-right', 'Hidden Lead actions right aligned')
req(leads,'focus-list-search', 'Hidden Lead search shortened')

contacts=t('templates/portal/contacts.html')
req(contacts,'name="focus"', 'Address Book Focus facet')
req(contacts,'All items', 'Address Book read-state default wording')
req(contacts,'focus-list-search', 'Address Book search shortened')
forbid(contacts,'toolbar-actions-right', 'Address Book actions must not move')

for untouched in ('templates/portal/blacklist.html','templates/portal/applications.html'):
    if (R/untouched).exists(): forbid(t(untouched),'toolbar-actions-right',untouched+' actions must not move')

base=t('templates/portal/base.html')
req(base,"const companyFilterDefaultPrompt='Select filters, then click Apply.'", 'short filter prompt')
req(base,"setCompanyFilterPrompt(modal,'Review selections, then click Apply.')", 'short preset prompt')
req(base,'function initScoutMultilineTooltips()', 'viewport tooltip implementation')
req(base,"tip.className='scout-floating-tooltip'", 'body-level tooltip')
req(base,'document.body.appendChild(tip)', 'tooltip outside table layout')
req(base,'if(top+tr.height>window.innerHeight-pad)top=r.top-tr.height-gap', 'tooltip flips above near viewport bottom')
req(base,"wrap.classList.add('focus-filter-wrap')", 'Focus searchable-select width hook')

css=t('portal/static/portal/app.css')
req(css,'.scout-floating-tooltip{position:fixed', 'fixed tooltip')
req(css,'.scout-multiline-tooltip::after{content:none!important', 'old layout tooltip disabled')
req(css,'font-weight:400!important', 'tooltip normal weight')
req(css,'.toolbar-actions-right{', 'right action group CSS')
req(css,'.focus-filter-wrap{width:180px', 'Focus facet width')

fresh=t('portal/services/freshness.py')
req(fresh,"if raw=='~1 week': return '< 1 week'", 'legacy one-week label normalized')
req(fresh,"if days<10: return '< 1 week'", 'freshest age display')
extras=t('portal/templatetags/portal_extras.py')
start=extras.index('def post_age_provenance_tooltip')
end=extras.find('\ndef ',start+5)
post=extras[start:end if end!=-1 else None]
req(post,"lines.append('Evidence: '+", 'Post Age Evidence label')
forbid(post,"lines.append('Reason:", 'Post Age Reason label removed')

apps=t('opportunity_portal/settings.py')
req(apps,"'portal.apps.PortalConfig'", 'Focus post-save signals enabled')

for active in ('portal/services/ai.py','portal/services/company_research.py','portal/services/notifications.py'):
    text=t(active)
    if '0.10.100' in text:
        raise SystemExit('FAIL stale active release version in '+active)

for pth in list((R/'portal').rglob('*.py')) + list((R/'scripts').rglob('*.py')) + list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(), filename=str(pth))
print('ScoutBox 0.10.101 targeted regressions passed.')
