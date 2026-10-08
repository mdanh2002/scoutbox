#!/usr/bin/env python3
from pathlib import Path
import ast

R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.100'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.100'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.100'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.100'

extras=t('portal/templatetags/portal_extras.py')
req(extras,'def _company_registration_evidence(', 'legacy/partial registration evidence recovery')
req(extras,"label not in {'domain age','domain created'",'domain fact fallback parsing')
req(extras,"structured=_company_registration_evidence(intel,structured)",'registration evidence used by badge')
req(extras,'class="company-domain-year-line"','supplemental globe/year line retained')
req(extras,'company-domain-year-mini-globe','crisp mini globe retained')
req(extras,"domain_lines.append(f'Domain created: {created_detail}')",'domain created tooltip')

css=t('portal/static/portal/app.css')
req(css,'font-weight:400!important;line-height:1.45;text-align:left','structured tooltip normal font weight')

research=t('portal/services/company_research.py')
req(research,'def _company_identity_key(', 'normalized company identity key')
req(research,'def _company_lookup_variants(', 'spacing variant cache reuse')
req(research,'def _domain_company_match_score(', 'strong domain/company matching')
req(research,"len(stem)/max(1,len(key))>=0.75",'partial-domain rejection threshold')
req(research,"for company_variant in _company_lookup_variants(company):",'cache reuse across spacing variants')
forbid(research,"token_match=any(",'old any-token domain acceptance')
req(research,"'User-Agent':'ScoutBox/0.10.100'",'current RDAP user agent')

migration=t('portal/migrations/0120_v010100_company_domain_evidence_reuse.py')
req(migration,'def reuse_known_domain_evidence(', 'local domain evidence migration')
req(migration,"dependencies=[('portal','0119_v01098_company_domain_tooltip_repair')]",'migration dependency')
forbid(migration,'requests.', 'migration must not use network')

for active in ('portal/services/ai.py','portal/services/company_research.py','portal/services/notifications.py'):
    text=t(active)
    if '0.10.99' in text:
        raise SystemExit('FAIL stale active release version in '+active)

for pth in list((R/'portal').rglob('*.py')) + list((R/'scripts').rglob('*.py')) + list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(), filename=str(pth))
print('ScoutBox 0.10.100 targeted regressions passed.')
