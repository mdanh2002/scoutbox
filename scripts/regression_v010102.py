#!/usr/bin/env python3
from pathlib import Path
import ast, re
R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.102'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.102'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.102'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.102'

models=t('portal/models.py')
req(models,"focus_comparison_records = models.PositiveSmallIntegerField(default=100",'Focus comparison default')
req(models,"max_focus_groups = models.PositiveSmallIntegerField(default=15",'Focus group default')
req(models,"focus_taxonomy_version = models.CharField",'Focus rebuild release marker')

focus=t('portal/services/focus.py')
req(focus,"replace('/',' and ')",'slash-free AI label sanitizer')
req(focus,'_ai_choose_focus','AI Focus naming')
req(focus,'Local AI','local AI Focus path')
req(focus,'MUST NOT contain slash characters','AI prompt avoids mechanical slash names')
req(focus,'rebuild_all_focus_taxonomies_with_ai','one-time full AI rebuild')
req(focus,'model.objects.update(focus=\'\')','old Focus taxonomy cleared')
req(focus,'runtime comparison depth is ignored','upgrade rebuild ignores normal sample limit')
req(focus,'rebalance_focus_taxonomy_once(model,max_groups)','configured group cap convergence')
forbid(focus,'cloud_ai','Focus must not invoke Cloud AI')
forbid(focus,'requests.','Focus naming must not perform public network requests')

mig=t('portal/migrations/0122_v010102_focus_ai_rebuild.py')
req(mig,"Opportunity.objects.update(focus='')",'Opportunity Focus reset')
req(mig,"CompanyLead.objects.update(focus='')",'Hidden Lead Focus reset')
req(mig,"Contact.objects.update(focus='')",'Address Book Focus reset')
forbid(mig,'ollama.','schema migration must not call AI')
forbid(mig,'requests.','schema migration must not call network')

tasks=t('portal/tasks.py')
req(tasks,"label='Rebuild Focus taxonomy for 0.10.102'",'one-time Focus rebuild job')
req(tasks,"ps.focus_taxonomy_version='0.10.102'",'Focus rebuild completion marker')

settings=t('templates/portal/settings.html')
req(settings,'name="focus_comparison_records"','Focus comparison setting')
req(settings,'name="max_focus_groups"','Focus cap setting')

base=t('templates/portal/base.html')
req(base,'id="list-loading-spinner"','global list loading indicator')
req(base,'function setListBusy(on)','list loading state')
req(base,'function navigateListFacet(name,value)','reliable server facet navigation')
req(base,"function toggleServerFailedUrls(checked)",'server Hide failed URLs')
req(base,'table.dataset.countOnly','count-only list footer support')
req(base,"wrap.classList.add('focus-filter-wrap')",'Focus selector sizing hook')

css=t('portal/static/portal/app.css')
req(css,'.focus-filter-wrap{width:300px','wider Focus selector')
req(css,'.list-loading-spinner','loading spinner CSS')
req(css,'.list-footer-three','three-part list footer')
req(css,'.list-footer-two','two-part list footer')
req(css,'.deleted-row-note{margin-top:10px','blank spacing before Deleted on')
req(css,'.summary-url-health{margin-left:6px','HTTP status badge summary spacing')

opp=t('templates/portal/opportunities.html')
req(opp,'Hide failed URLs','Opportunity bottom health checkbox')
req(opp,'summary-url-health','Opportunity health badge in Summary')
req(opp,'toolbar-actions-right','Opportunity actions right')
req(opp,'All focuses','Opportunity Focus filter')
forbid(opp,'All statuses','Opportunity status facet removed')

leads=t('templates/portal/cold_contact.html')
req(leads,'Hide failed URLs','Hidden Lead bottom health checkbox')
req(leads,'summary-url-health','Hidden Lead health badge in Summary')
req(leads,'toolbar-actions-right','Hidden Lead actions right')

contacts=t('templates/portal/contacts.html')
req(contacts,"onchange=\"navigateListFacet('focus',this.value)\"",'Address Book Focus filter navigation')
req(contacts,'Hide failed URLs','Address Book bottom health checkbox')
req(contacts,'data-count-only="1"','Address Book count without page x/y')
req(contacts,'toolbar-actions-right','Address Book actions right')
req(contacts,'data-pager-info="contacts-table"','Address Book count bottom right')

blacklist=t('templates/portal/blacklist.html')
req(blacklist,'toolbar-actions-right','Blacklist actions right')
req(blacklist,'list-footer-two','Blacklist compact footer')
forbid(blacklist,'· page {{page_obj.number}} / {{page_obj.paginator.num_pages}}','Blacklist page x/y count removed')

campaigns=t('templates/portal/campaigns.html')
if campaigns.count('toolbar-actions-right')<2: raise SystemExit('FAIL Campaign and Template actions not both right aligned')
if campaigns.count('data-count-only="1"')<2: raise SystemExit('FAIL Campaign/Template count-only footers missing')
if campaigns.count('list-footer-two')<2: raise SystemExit('FAIL Campaign/Template bottom controls missing')

apps=t('templates/portal/applications.html')
search_i=apps.index('applications-search'); country_i=apps.index('applications-country-filter'); action_i=apps.index('toolbar-actions-right')
if not (search_i < country_i < action_i): raise SystemExit('FAIL Applications filters/actions toolbar ordering')

views=t('portal/views.py')
req(views,"hide_non_200=(request.GET.get('healthy') or '')=='1'",'Address Book health filter request')
req(views,'Q(domain_http_status__isnull=True)|Q(domain_http_status=200)','Address Book failed URL filtering')
req(views,"user_deleted=True,deleted_at=now,is_read=True,rejection_reason='Blocked by user blacklist.'",'Selected blacklisted opportunities enter Recycle Bin')
req(views,'Application.objects.filter(opportunity_id__in=affected_ids,deleted_at__isnull=True).update(deleted_at=now','related applications remain recoverable')

bl=t('portal/services/blacklist.py')
req(bl,'user_deleted=True,','Blacklist enforcement recycles Opportunities')
req(bl,'deleted_at=now,','Blacklist enforcement timestamps recycle')
req(bl,'Application.objects.filter(opportunity_id=row.pk','Blacklist enforcement recycles related application')

extras=t('portal/templatetags/portal_extras.py')
req(extras,"'fully_remote':0,'remote':1,'hybrid':1,'onsite':2,'not_remote':2,'unknown':3",'useful Remote sort order')
req(extras,"lines.append('Evidence: '+",'Post Age evidence label')
req(extras,"obvious_tokens.issubset",'obvious datePosted/schema evidence hidden')
forbid(extras,"lines.append('Reason:",'Reason label removed')

fetch=t('portal/services/pagefetch.py')
req(fetch,'stream=True','stream direct page fetch')
req(fetch,"'skipped_binary':False",'binary skip diagnostic')
req(fetch,"binary_exts=('.pdf'",'PDF/binary short-circuit')
req(fetch,"max_body=2_500_000",'bounded HTML fetch')
forbid(fetch,"result['bytes']=len(r.content)",'no eager direct response download')

# Active release clients should identify the current build.
for active in ('portal/services/ai.py','portal/services/company_research.py','portal/services/notifications.py'):
    if '0.10.101' in t(active): raise SystemExit('FAIL stale active release version in '+active)

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py'))+list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.102 targeted regressions passed.')
