#!/usr/bin/env python3
from pathlib import Path
import ast, re
R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.110'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.110'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.110'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.110'
assert (R/'docs'/'RELEASE_NOTES_0.10.110.md').is_file()

focus=t('portal/services/focus.py')
req(focus,"('Machine Learning'",'machine learning residual topic')
req(focus,"('Technical Support'",'technical support residual topic')
req(focus,"('GTM Analytics'",'gtm analytics residual topic')
req(focus,"('Healthcare Research'",'healthcare research residual topic')
req(focus,"('FinTech Engineering'",'fintech residual topic')
req(focus,"('Data Analytics'",'data analytics residual topic')
req(focus,"('Cloud DevOps'",'cloud devops residual topic')
req(focus,'_USEFUL_EXACT_LABELS', 'useful exact labels whitelist')
req(focus,'source != \'topic_rule\'', 'topic-rule umbrella assignment support')
req(focus,'if len(mapping) < int(total*0.90)', 'higher residual prototype target')
req(focus,'if len(mapping) < int(total*0.86)', 'residual fill target')
req(focus,'10-15% Unclassified ceiling', 'residual pass rationale')
req(focus,"'release':'0.10.110'", 'focus provenance release stamp')
forbid(focus,"r'\x08",'regex backspace corruption')
forbid(focus,'def _campaign_focus_choice', 'campaign dominance remains removed')

mig=t('portal/migrations/0130_v010110_focus_residual_footer.py')
req(mig,'focus_residual_release', 'migration records residual repair')
req(mig,'repair_model_focus_taxonomy(Opportunity,target,rewrite=True)', 'opportunity repair')
req(mig,'repair_model_focus_taxonomy(CompanyLead,target,rewrite=True)', 'hidden lead repair')
req(mig,'repair_model_focus_taxonomy(Contact,target,rewrite=True)', 'address book repair')
req(mig,"ps.focus_taxonomy_version='0.10.110'", 'migration stamps taxonomy version')

opp=t('templates/portal/opportunities.html')
lead=t('templates/portal/cold_contact.html')
contacts=t('templates/portal/contacts.html')
for name,html,kind in [('opportunities',opp,'opportunities'),('hidden leads',lead,'hidden-leads'),('contacts',contacts,'contacts')]:
    req(html,'hide-failed-footer', name+' footer hide failed')
    forbid(html,'<div class="pager-center"><label class="hide-failed-footer', name+' center hide failed removed')
req(opp,'opportunity-list-footer list-footer-two', 'opportunity footer two-column')
req(lead,'list-footer-pager list-footer-two', 'hidden lead footer two-column')
req(contacts,'<div class="list-footer-two"><div class="pager-left"><label>Rows', 'contact footer two-column')
css=t('portal/static/portal/app.css')
req(css,'0.10.110 — residual Focus quality and footer Failed URL placement', '0.10.110 CSS block')
req(css,'.opportunity-list-footer.list-footer-two', 'opportunity footer CSS')
req(css,'#contacts-bulk .list-footer-two', 'contacts footer CSS')

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py'))+list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.110 targeted regressions passed.')
