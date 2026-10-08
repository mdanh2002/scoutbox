#!/usr/bin/env python3
from pathlib import Path
import ast

R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text, needle, label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))

def forbid(text, needle, label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.98'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.98'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.98'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.98'

extras=t('portal/templatetags/portal_extras.py')
req(extras,"structured.get('company_domain')",'tooltip reads company_domain')
req(extras,"structured.get('company_website')",'tooltip reads company website')
req(extras,"label in {'domain','website','company website','official website','homepage','home page'}",'tooltip reads domain facts')
req(extras,"intel.get('sources')",'tooltip can use stored official sources')
req(extras,"Domain age: {domain_age_tooltip}",'consistent domain age line')
forbid(extras,"Domain age (registration/RDAP):",'old RDAP-specific tooltip wording')

research=t('portal/services/company_research.py')
req(research,'def _discover_company_domain_from_search','bounded official-domain repair')
req(research,"query=f'\"{company}\" official website'",'official website lookup')
req(research,"structured['company_domain']=discovered",'persist discovered company domain')
req(research,"structured['domain_age_refresh_needed']=True",'missing domain remains repairable')
req(research,"('Website','website')",'cloud result preserves official website')
req(research,"'website','company_website','company_domain','domain'",'normalization preserves website/domain fields')
req(research,"'User-Agent':'ScoutBox/0.10.98'",'RDAP version user agent')

migration=t('portal/migrations/0119_v01098_company_domain_tooltip_repair.py')
req(migration,'def mark_company_domain_refresh','upgrade requeues missing domains')
req(migration,"st['domain_age_refresh_needed'] = True",'upgrade marker')

for active in ('portal/services/ai.py','portal/services/company_research.py','portal/services/notifications.py'):
    text=t(active)
    if '0.10.97' in text:
        raise SystemExit('FAIL stale active release user-agent/version in '+active)

for pth in list((R/'portal').rglob('*.py')) + list((R/'scripts').rglob('*.py')) + list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.98 targeted regressions passed.')
