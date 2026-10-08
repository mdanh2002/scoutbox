#!/usr/bin/env python3
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]
def t(p): return (R/p).read_text()
def req(s,x,label=''):
    if x not in s: raise SystemExit('FAIL missing '+(label or x))
assert t('VERSION').strip()=='0.10.94'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.94'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.94'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.94'

settings=t('opportunity_portal/settings.py')
req(settings,"'retention-cleanup-tick'",'daily retention cleanup schedule')
models=t('portal/models.py')
req(models,'detailed_log_retention_days = models.PositiveSmallIntegerField(default=90','90-day detailed-log retention')
req(models,'scheduler_health = models.JSONField','scheduler health persistence')
req(models,'origin_provenance = models.JSONField','contact provenance persistence')

tasks=t('portal/tasks.py')
for token,label in (
    ("scoutbox:scheduler_tick:v01094",'Redis scheduler ownership lease'),
    ("scheduler_tick_duplicate_db_claim",'database duplicate scheduler claim'),
    ("SCOUTBOX_FORUM_BROWSE_INTERVAL_MINUTES','5'",'five-minute Forum cadence'),
    ("queue='forum'",'dedicated Forum worker queue'),
    ('def retention_cleanup_tick','daily retention task'),
    ('company_research_requeued_ids','company-research recovery'),
    ("'accepted':True,'provider_message_id'",'digest provider acceptance semantics'),
): req(tasks,token,label)

fresh=t('portal/services/fresh_sources.py')
for token,label in (
    ('timestamp()//300','five-minute Forum source rotation'),
    ("and accepted:",'zero-result Forum pass continues'),
    ("'class':'access_denied'",'403 cooldown class'),
    ("'class':'rate_limited'",'429 cooldown class'),
    ("'accepted_by_source'",'Forum useful-candidate diagnostics'),
): req(fresh,token,label)

role=t('portal/services/role_gate.py')
for token,label in (
    ('_hard_role_source_reject','hard Opportunity source gate'),
    ("host=='gist.github.com'",'GitHub Gist dataset rejection'),
    ("'hard_reject':True",'non-overridable hard reject'),
): req(role,token,label)

discovery=t('portal/services/discovery.py')
req(discovery,'def _deterministic_company_from_evidence','deterministic employer recovery')
req(discovery,"if role_gate.get('hard_reject')",'hard gate enforced before persistence')

notifications=t('portal/services/notifications.py')
req(notifications,"event.delivery_status='accepted'",'provider acceptance state')
req(notifications,'def refresh_resend_delivery_states','Resend delivery refresh')

views=t('portal/views.py')
req(views,'ps.detailed_log_retention_days=max(14,min(180','retention setting clamp')
req(views,'Search-provider aggregates and business records were preserved','manual Clear Logs preserves aggregates')
req(views,'cpu_min','resource min/avg/max')

base=t('templates/portal/base.html')
req(base,'function rowVisibleText(row)','visible-cell-only table search')
req(base,"filter.placeholder='Search visible fields…'",'automatic list search box')
req(base,"paginate||table.hasAttribute('data-sort-table')",'search box on list and sortable list views')
if 'r.dataset.search||r.textContent' in base:
    raise SystemExit('FAIL list search still uses hidden data-search metadata')

opps=t('templates/portal/opportunities.html'); leads=t('templates/portal/cold_contact.html')
if 'Hide failed URLs' in opps or 'Hide failed URLs' in leads:
    raise SystemExit('FAIL Hide failed URLs toolbar control still present')

extras=t('portal/templatetags/portal_extras.py')
req(extras,"domain_lines.append(f'Domain: {domain}')",'Company Info domain tooltip')
req(extras,"domain_lines.append(f'Domain age: {domain_age_tooltip or \"Unknown\"}')",'Company Info domain-age tooltip')

mail=t('templates/portal/email_config.html')
req(mail,'mail-test-body-row','outgoing-test body alignment/height hook')
css=t('portal/static/portal/app.css')
req(css,'.mail-test-body-row textarea{min-height:160px','outgoing-test body height')
req(css,'.btn:not(:disabled):active','consistent button active state')

migration=t('portal/migrations/0117_v01094_scheduler_retention_provenance.py')
req(migration,'repair_recent_opportunity_identity','upgrade data repair')
req(migration,"AuditLog.objects.filter(action='addressbook_promotion').delete()",'promotion audit cleanup')

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.94 targeted regressions passed.')
