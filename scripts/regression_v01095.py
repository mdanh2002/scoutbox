#!/usr/bin/env python3
from pathlib import Path
import ast,re
R=Path(__file__).resolve().parents[1]
def t(p): return (R/p).read_text()
def req(s,x,label=''):
    if x not in s: raise SystemExit('FAIL missing '+(label or x))
def forbid(s,x,label=''):
    if x in s: raise SystemExit('FAIL present '+(label or x))

assert t('VERSION').strip()=='0.10.95'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.95'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.95'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.95'

settings=t('opportunity_portal/settings.py')
req(settings,"'retention-cleanup-tick'",'daily retention cleanup schedule')
req(settings,"'company-domain-refresh-tick'",'deterministic domain refresh schedule')

base=t('templates/portal/base.html')
req(base,'function rowVisibleText(row)','visible-cell-only client search')
req(base,"const filter=document.querySelector('[data-table-filter=\"'+id+'\"]')",'existing search controls only')
forbid(base,"filter.placeholder='Search visible fields…'",'0.10.94 automatic search injection')
forbid(base,'r.dataset.search||r.textContent','hidden data-search matching')

campaign_detail=t('templates/portal/campaign_detail.html')
# Query Rotation had no search in 0.10.93 and must not gain one in 0.10.95.
rotation=campaign_detail.split('Query Rotation',1)[1] if 'Query Rotation' in campaign_detail else campaign_detail
if 'data-table-filter="rotation-table"' in rotation:
    raise SystemExit('FAIL Query Rotation search box still present')

views=t('portal/views.py')
req(views,'visible_match=(', 'server visible-field search predicates')
if 'description__icontains=q' in views[views.find('def opportunities_view'):views.find('def opportunity_detail') if 'def opportunity_detail' in views else len(views)]:
    raise SystemExit('FAIL Opportunity list search still matches hidden description')
req(views,"_sample_at=Max('at')",'non-conflicting long-range resource time alias')

if re.search(r'(?m)^\s*at=Max\(\'at\'\),\s*$',views):
    raise SystemExit('FAIL resource model-field annotation collision')
req(views,"logger.exception('Resource Usage aggregation failed; using bounded raw fallback')",'observable resource aggregation fallback')
req(views,"cpu_min=Min('cpu_percent')",'resource min/max preservation')

settings_html=t('templates/portal/settings.html')
forbid(settings_html,'business records and aggregate statistics are preserved','retention helper sentence')
req(settings_html,'detailed_log_retention_days','retention setting remains present')
models=t('portal/models.py')
req(models,'detailed_log_retention_days = models.PositiveSmallIntegerField(default=90','90-day default retention')

company=t('portal/services/company_research.py')
req(company,'def refresh_company_domain_registration','deterministic domain maintenance')
req(company,"structured['domain_age_domain']=domain",'domain persisted independently of RDAP age')
req(company,"structured['domain_age_checked_at']=timezone.now().isoformat()",'RDAP retry throttle evidence')
req(company,"CompanyResearchCache.objects.filter(company__iexact=company)",'same-company domain cache reuse')
req(company,'CompanyResearchCache.objects.update_or_create','normalized-domain cache reuse')
req(company,"'website','company_website','company_domain','domain'",'official domain hints preserved')
req(company,"'User-Agent':'ScoutBox/0.10.95'",'domain lookup release user-agent')

lifecycle=t('portal/services/ai_lifecycle.py')
company_block=lifecycle[lifecycle.find("if kind=='company':"):lifecycle.find("if kind=='freshness':")]
forbid(company_block,"if structured.get('domain_age_refresh_needed'):\n            return False",'domain refresh forcing another AI pass')

tasks=t('portal/tasks.py')
req(tasks,'def company_domain_refresh_tick','bounded domain maintenance task')
req(tasks,'refresh_company_domain_registration','domain maintenance service call')
req(tasks,'timedelta(hours=6)','RDAP retry throttle')

extras=t('portal/templatetags/portal_extras.py')
req(extras,"domain_lines.append(f'Domain: {domain}')",'Company Info Domain tooltip line')
req(extras,"domain_lines.append(f'Domain age: {domain_age_tooltip or \"Unknown\"}')",'Company Info Domain age tooltip line')

css=t('portal/static/portal/app.css')
req(css,'.btn.primary:not(:disabled):hover{background:','background-only primary hover')
for m in re.finditer(r'([^{}]+:hover[^{}]*)\{([^{}]*)\}',css):
    selector=' '.join(m.group(1).split()); body=m.group(2)
    if any(k in selector for k in ('.btn','.icon-btn','history-launch','company-info-refresh-icon','export-docx-icon')):
        if 'border-color' in body:
            raise SystemExit('FAIL button-like hover changes border: '+selector[:120])
        if 'translateY(' in body or 'translateX(' in body:
            raise SystemExit('FAIL button-like hover translates control: '+selector[:120])

# Digest subject: same for scheduled/manual, dated, count based, no TEST/legacy wording.
digest=t('portal/services/digest.py')
req(digest,"strftime('%d %b %Y')",'local digest send date')
req(digest,"f'[{local_send_date}] - Daily Digest ['",'dated digest subject')
req(digest,'_count_phrase(opportunity_total,"opportunity","opportunities","new ")','opportunity total subject count')
req(digest,'_count_phrase(lead_total,"lead","leads","new ")','lead total subject count')
req(digest,'_count_phrase(contact_total,"contact","contacts")','contact total subject count')
subject_area=digest[digest.find('local_send_date='):digest.find('plain_lines=') if 'plain_lines=' in digest else len(digest)]
if 'TEST — ScoutBox 24-hour digest' in subject_area or "subject='ScoutBox 24-hour digest'" in subject_area:
    raise SystemExit('FAIL legacy/test Daily Digest subject remains')

migration=t('portal/migrations/0118_v01095_corrective_release.py')
req(migration,"delivery_status='sent'",'legacy Resend sent selector')
req(migration,"row.delivery_status='accepted'",'legacy Resend accepted normalization')
req(migration,'def mark_missing_domain_refresh','pre-0.10.95 domain refresh re-marking')

notifications=t('portal/services/notifications.py')
req(notifications,"event.delivery_status='accepted'",'provider acceptance semantics')
req(notifications,"'User-Agent':'ScoutBox/0.10.95'",'Resend status release user-agent')

opps=t('templates/portal/opportunities.html'); leads=t('templates/portal/cold_contact.html')
if 'Hide failed URLs' in opps or 'Hide failed URLs' in leads:
    raise SystemExit('FAIL Hide failed URLs toolbar control returned')

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py'))+list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.95 targeted regressions passed.')
