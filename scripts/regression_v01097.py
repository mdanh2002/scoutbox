#!/usr/bin/env python3
from pathlib import Path
import ast

R = Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text, needle, label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text, needle, label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip() == '0.10.97'
assert t('RELEASE_ID').strip() == 'ScoutBox v0.10.97'
assert t('BUILD_INFO.txt').strip() == 'ScoutBox v0.10.97'
assert t('README.md').splitlines()[0].strip() == '# ScoutBox 0.10.97'

extras=t('portal/templatetags/portal_extras.py')
req(extras, "details.extend(domain_lines)", 'consistent Domain/Domain age tooltip lines')
req(extras, "if domain_age_tooltip:\n        domain_lines.append(f'Domain age: {domain_age_tooltip}')", 'domain age shown whenever resolved')
req(extras, "if age and age_kind!='domain':", 'company age only when actual company age is known')
req(extras, "details.append(f'Company size: {size} employees')", 'company employee-size range')
forbid(extras, "details.append('Domain age (registration/RDAP): '+age)", 'old domain-only tooltip wording')
req(extras, "company_name=clean_company(intel.get('company') or '')", 'company name fallback to company intel')

css=t('portal/static/portal/app.css')
req(css, '#settings-general .portal-root-compact-field{\n  display:flex;', 'portal root flex layout')
req(css, 'gap:8px;', 'portal root textbox/button gap')
req(css, '#settings-general .portal-root-compact-field #portal-root-url{\n  flex:1 1 auto;', 'shortened flexible URL textbox')
req(css, '#settings-general .portal-root-compact-field .portal-root-detect{\n  position:static;', 'Auto-detect no longer overlays textbox')
forbid(css, 'padding-right:101px!important;', 'old embedded-button padding')

for active in ('portal/services/ai.py','portal/services/company_research.py','portal/services/notifications.py'):
    text=t(active)
    if '0.10.96' in text:
        raise SystemExit('FAIL stale active release user-agent/version in '+active)

for pth in list((R/'portal').rglob('*.py')) + list((R/'scripts').rglob('*.py')) + list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(), filename=str(pth))
print('ScoutBox 0.10.97 targeted regressions passed.')
