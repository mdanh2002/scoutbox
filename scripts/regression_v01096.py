#!/usr/bin/env python3
from pathlib import Path
import ast
import re

R = Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text, needle, label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text, needle, label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip() == '0.10.96'
assert t('RELEASE_ID').strip() == 'ScoutBox v0.10.96'
assert t('BUILD_INFO.txt').strip() == 'ScoutBox v0.10.96'
assert t('README.md').splitlines()[0].strip() == '# ScoutBox 0.10.96'

extras = t('portal/templatetags/portal_extras.py')
req(extras, "if age_kind!='domain':\n        details.extend(domain_lines)", 'supplement domain lines only on company-age badge')
req(extras, "details.append('Domain age (registration/RDAP): '+age)", 'domain/RDAP primary age remains visible')

settings_html = t('templates/portal/settings.html')
req(settings_html, 'class="digest-time-actions"', 'digest time action alignment wrapper')
req(settings_html, 'class="btn digest-test-button"', 'test digest moved beside digest time')
req(settings_html, 'class="field-with-action portal-root-compact-field"', 'portal root integrated control')
# Bottom action row must contain only Save configuration.
bottom = settings_html.split('Keep detailed logs for', 1)[1].split('</form>', 1)[0]
if bottom.count('Send Test Digest Email'):
    raise SystemExit('FAIL test digest button still in bottom action row')

css = t('portal/static/portal/app.css')
req(css, '#settings-general .digest-time-actions{', 'digest time aligned width')
req(css, 'width:420px!important;', '420px settings alignment')
req(css, '#settings-general .portal-root-compact-field .portal-root-detect{', 'Auto-detect integrated into URL field')
req(css, 'position:absolute;', 'Auto-detect positioned inside URL field')
req(css, 'padding-right:101px!important;', 'URL input reserves embedded button space')

digest = t('portal/services/digest.py')
req(digest, "f'[{local_send_date}] - Daily Digest ('", 'digest count parentheses open')
req(digest, "f'{_count_phrase(contact_total,\"contact\",\"contacts\")})'", 'digest count parentheses close')
forbid(digest, "f'[{local_send_date}] - Daily Digest ['", 'old nested square count group')
req(digest, 'class="stats-table"', 'email-safe operational table')
req(digest, 'width="{width}%"', 'explicit metric table column widths')
req(digest, 'role="presentation" width="100%" cellpadding="0" cellspacing="0"', 'email-safe table attributes')
forbid(digest, 'class="stats-grid"', 'CSS-grid operational summary')

for active in ('portal/services/ai.py','portal/services/company_research.py','portal/services/notifications.py'):
    text=t(active)
    if '0.10.95' in text:
        raise SystemExit('FAIL stale active release user-agent/version in '+active)

for pth in list((R/'portal').rglob('*.py')) + list((R/'scripts').rglob('*.py')) + list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(), filename=str(pth))
print('ScoutBox 0.10.96 targeted regressions passed.')
