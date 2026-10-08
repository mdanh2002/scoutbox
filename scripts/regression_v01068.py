#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def fail(msg):
    raise SystemExit(f'FAIL: {msg}')

if read('VERSION').strip() != '0.10.68':
    fail('VERSION is not 0.10.68')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.68':
    fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.68':
    fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.68'):
    fail('README stale')
if not (ROOT / 'docs' / 'RELEASE_NOTES_0.10.68.md').exists():
    fail('release notes missing')

chat = read('portal/services/chatbot.py')
if 'GENERIC_CHAT_BUTTON_LABELS' not in chat:
    fail('generic chat button filter missing')
if "returnsnapshot,[]" not in chat.replace(' ', ''):
    fail('build_context still appears to return default shortcut links')
if 'merged[:6]' in chat or "('Open Candidate Profile','profile')" in chat:
    fail('old broad chat shortcut link bar still present')
if '_fallback_navigation_links' not in chat or '_compact_action_links' not in chat:
    fail('fallback action link helpers missing')
if 'Web source {idx}' in chat:
    fail('web source buttons should not be appended automatically')

base = read('templates/portal/base.html')
if 'visibleLinks(links)' not in base:
    fail('chat UI visibleLinks filter missing')
if 'if(out.length>=2)break' not in base:
    fail('chat UI action link cap missing')
if 'Open Candidate Profile' not in base or 'Open Configuration Maintenance' not in base:
    fail('legacy generic button labels are not filtered in UI')
if 'links:Array.isArray(links)?links:[]' in base:
    fail('chat UI still persists unfiltered link arrays')
if 'links:this.visibleLinks(x.links||[])' not in base:
    fail('server chat history links are not filtered before local transcript persistence')

verify = read('verify_release.sh')
if 'regression_v01068.py' not in verify:
    fail('verify_release does not run v01068 regression')
print('ScoutBox 0.10.68 targeted regressions passed.')
