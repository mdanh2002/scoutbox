#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

if read('VERSION').strip() != '0.10.69':
    fail('VERSION is not 0.10.69')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.69':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.69':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.69'):
    fail('README version stale')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.69.md').is_file():
    fail('0.10.69 release notes missing')

brand = ROOT / 'docs' / 'branding' / 'scoutbox-brand-concept.png'
logo = ROOT / 'portal' / 'static' / 'portal' / 'scoutbox-logo.png'
if brand.stat().st_size >= 1_900_000:
    fail('branding concept image was not compressed enough')
if logo.stat().st_size >= 700_000:
    fail('logo image was not compressed enough')

template = read('templates/portal/base.html')
if "fullscreen:p?p.classList.contains('fullscreen')" in template:
    fail('chatbot fullscreen state is still persisted')
if "if(p&&state.fullscreen)p.classList.add('fullscreen')" in template:
    fail('chatbot reload still restores fullscreen state')
if "if(p){p.classList.remove('fullscreen');if(state.open)p.hidden=false}" not in template:
    fail('chatbot load does not clear stale fullscreen state')
if "const closing=!p.hidden;if(closing)p.classList.remove('fullscreen');p.hidden=closing" not in template:
    fail('chatbot close does not leave fullscreen before saving state')

bad = [p for p in ROOT.rglob('*') if p.name == '__pycache__' or p.suffix == '.pyc']
if bad:
    fail('bytecode cache files/directories present: ' + ', '.join(str(p.relative_to(ROOT)) for p in bad[:5]))

print('ScoutBox 0.10.69 targeted regressions passed.')
