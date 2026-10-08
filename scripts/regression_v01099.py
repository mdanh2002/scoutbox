#!/usr/bin/env python3
from pathlib import Path
import ast

R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.99'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.99'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.99'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.99'

extras=t('portal/templatetags/portal_extras.py')
req(extras, 'def _company_domain_mini_svg():', 'small vector globe helper')
req(extras, 'shape-rendering="geometricPrecision"', 'vector precision for small globe')
req(extras, "domain_lines.append(f'Domain created: {created_detail}')", 'domain creation tooltip wording')
req(extras, "if age_kind=='domain':", 'domain-only badge rendering')
req(extras, "line_parts.append(f'<span>{escape(domain_created_year)}</span>')", 'domain-only creation year')
req(extras, 'class="company-domain-year-line"', 'supplemental company badge domain year line')
forbid(extras, "domain_lines.append(f'Domain age:", 'old domain age tooltip wording')
req(extras, "tooltip_lines=[f'Remote: {label}']", 'multiline remote tooltip')
req(extras, "tooltip_lines.append(f'Confidence: {confidence}%')", 'remote confidence line')
req(extras, "tooltip_lines.append(f'Reason: {reason[:240]}')", 'remote reason line')
forbid(extras, "title=f'{label} ·", 'old dotted remote tooltip')
req(extras, "lines.append('Reason: '+reason[:260])", 'post age reason line')

opp=t('templates/portal/opportunities.html')
req(opp, 'post-age-list {{o|post_age_quality}} scout-multiline-tooltip', 'styled post-age tooltip')
req(opp, 'data-tooltip="{{o|post_age_provenance_tooltip|escape}}"', 'post-age data tooltip')
forbid(opp, 'class="post-age-list {{o|post_age_quality}}" title=', 'old native post-age tooltip')

css=t('portal/static/portal/app.css')
req(css, '.company-domain-year-mini-globe{display:block;width:12px;height:12px;', 'clear 12px mini globe')
req(css, 'shape-rendering:geometricPrecision', 'CSS geometric precision')

for active in ('portal/services/ai.py','portal/services/company_research.py','portal/services/notifications.py'):
    text=t(active)
    if '0.10.98' in text:
        raise SystemExit('FAIL stale active release version in '+active)

for pth in list((R/'portal').rglob('*.py')) + list((R/'scripts').rglob('*.py')) + list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(), filename=str(pth))
print('ScoutBox 0.10.99 targeted regressions passed.')
