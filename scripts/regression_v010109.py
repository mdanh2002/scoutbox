#!/usr/bin/env python3
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.109'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.109'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.109'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.109'
assert (R/'docs'/'RELEASE_NOTES_0.10.109.md').is_file()

focus=t('portal/services/focus.py')
req(focus,"'Opportunity': 'opportunities'", 'Opportunity focus namespace')
req(focus,"'CompanyLead': 'hidden_leads'", 'Hidden Lead focus namespace')
req(focus,"'Contact': 'address_book'", 'Address Book focus namespace')
req(focus,'campaign can help name a cluster when the record', 'campaign inspiration documented')
req(focus,'def _candidate_phrases', 'dynamic phrase candidates')
req(focus,'campaign_supported', 'campaign-supported naming hints')
req(focus,'campaign_refined', 'campaign refined labels for broad campaign names')
req(focus,'def _min_group_size', 'minimum group size rules')
req(focus,'def _max_group_size', 'maximum group size rules')
req(focus,'def _select_balanced_labels', 'balanced label selection')
req(focus,'def _assign_records_to_labels', 'balanced assignment')
req(focus,'def taxonomy_quality_repair_needed', 'taxonomy quality detector')
req(focus,'Application Engineer, Software Engineer', 'generic label rejection prompt')
req(focus,"'release':'0.10.109'", 'focus provenance release stamp')
req(focus,"'namespace':_namespace_for_model", 'focus assignment provenance namespace')
req(focus,"('address_book',Contact)", 'address_book key used in all rebuild')
forbid(focus,'def _campaign_focus_choice', 'campaign-dominance focus assignment remains removed')
forbid(focus,'similarity>=0.055', 'weak similarity fallback remains removed')
forbid(focus,"('opportunities',Opportunity),('hidden_leads',CompanyLead),('contacts',Contact)", 'old contacts namespace removed')

mig=t('portal/migrations/0128_v010108_focus_balance.py')
req(mig,'v010108_balanced_taxonomy_repair', 'upgrade writes balanced repair provenance')
req(mig,"'address_book':repair_model(Contact", 'migration repairs address book independently')
req(mig,'balanced_focus_taxonomy_enabled', 'upgrade records balanced focus feature')
req(mig,"focus_namespaces']=['opportunities','hidden_leads','address_book']", 'upgrade stores focus namespaces')
req(mig,"status='stopped',message='Superseded by ScoutBox 0.10.109 balanced Focus taxonomy repair'", 'upgrade stops queued/running focus jobs')
req(mig,'campaign_supported', 'migration includes campaign-supported naming')
req(mig,'max_group(total,target)', 'migration checks oversized groups')
req(mig,'singletons>max', 'migration checks singleton-heavy groups')
req(mig,'is_generic_label', 'migration rejects generic labels')
forbid(mig,'requests.', 'migration must not call network')
forbid(mig,'ollama', 'migration must not call local AI')

tasks=t('portal/tasks.py')
req(tasks,"ps.focus_taxonomy_version='0.10.109'", 'tasks stamp 0.10.109 focus state')
req(tasks,"'release':'0.10.109','snapshot':snap", 'blank backfill metadata is 0.10.109')
req(tasks,"for key in ('opportunities','hidden_leads','address_book')", 'tasks use address_book namespace')

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py'))+list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.109 targeted regressions passed.')
