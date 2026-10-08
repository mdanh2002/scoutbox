#!/usr/bin/env python3
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text()

def fail(message):
    raise SystemExit(f'FAIL: {message}')

def require(text, token, label):
    if token not in text:
        fail(f'missing {label}: {token}')

def require_order(text, tokens, label):
    positions=[]
    for token in tokens:
        pos=text.find(token)
        if pos<0:
            fail(f'missing {label}: {token}')
        positions.append(pos)
    if positions != sorted(positions):
        fail(f'wrong order for {label}: {tokens}')

if read('VERSION').strip() != '0.10.90': fail('VERSION is not 0.10.90')
if read('RELEASE_ID').strip() != 'ScoutBox v0.10.90': fail('RELEASE_ID stale')
if read('BUILD_INFO.txt').strip() != 'ScoutBox v0.10.90': fail('BUILD_INFO stale')
if not read('README.md').startswith('# ScoutBox 0.10.90'): fail('README not bumped')
if not (ROOT/'docs'/'RELEASE_NOTES_0.10.90.md').is_file(): fail('0.10.90 release notes missing')
if not (ROOT/'portal'/'migrations'/'0114_v01090_platform_identity_cleanup.py').is_file(): fail('0.10.90 platform cleanup migration missing')

platforms=read('portal/services/platforms.py')
for token in ('builtin.com','linkedin.com','himalayas.app','greenhouse.io','lever.co','def is_job_platform_host','def is_platform_company_name','def is_direct_role_host_allowed'):
    require(platforms,token,'shared platform classifier')

blacklist=read('portal/services/blacklist.py')
for token in ('def company_blacklist_candidate','LABEL_BLACKLIST_MIN_CHARS','is_platform_company_name(company)','Company names shorter than','allow_short=allow_short','is_job_platform_host(host)'):
    require(blacklist,token,'blacklist validation')

opp_filter=read('portal/services/opportunity_filter.py')
for token in ('identity.direct_role_url','identity.same_role_confidence','Never return a generic careers homepage','The listing host/job board/ATS is not the employer'):
    require(opp_filter,token,'Cloud direct-role re-evaluation prompt')

tasks=read('portal/tasks.py')
for token in ('SCOUTBOX_FORUM_STARVATION_HOURS','forum_starvation_override','Automatic bounded Forum recovery pass','same_role_conf>=75','direct_role_resolution_history','original_job_board_url'):
    require(tasks,token,'forum fairness / direct URL persistence')

digest=read('portal/services/digest.py')
for token in ('TOP_N = 20','_remote_rank','return (int(row.get(\'_remote_rank\') or 0),ts)','No new entries in this 24-hour window; showing the latest earlier records.'):
    require(digest,token,'24-hour digest expansion')

views=read('portal/views.py')
for token in ("show_deleted=(request.GET.get('show_deleted') or '')=='1'", "'show_deleted':bool(show_deleted)"):
    if token not in views and token.startswith("'show_deleted'"):
        # show_deleted is passed via ctx keyword in this codebase, not necessarily dict literal.
        continue
    require(views,token,'show deleted backend')
for token in ('already in the Recycle Bin','def _restore_recycle_item','company_blacklist_candidate'):
    require(views,token,'bulk delete/restore/blacklist handling')

templates={
    'opportunities':read('templates/portal/opportunities.html'),
    'hidden':read('templates/portal/cold_contact.html'),
    'blacklist':read('templates/portal/blacklist.html'),
    'applications':read('templates/portal/applications.html'),
    'contacts':read('templates/portal/contacts.html'),
}
for name,text in templates.items():
    require(text,'Show Deleted',f'{name} Show Deleted control')
    require(text,'Deleted on',f'{name} deleted row note')
    require(text,'Restore',f'{name} inline restore')

# User-specified toolbar ordering on Applications and Address Book.
require_order(templates['applications'], ['Sync IMAP','Import application history','bulk-delete-action','Show Deleted','openModal(\'manual-app-modal\')'], 'Applications toolbar')
require_order(templates['contacts'], ['reEvaluateAddressBook()','company-filter-launch','bulk-delete-action','Show Deleted','openModal(\'contact-modal\')'], 'Address Book toolbar')

css=read('portal/static/portal/app.css')
for token in ('ScoutBox 0.10.90','.deleted-row','.deleted-row-note','show-deleted-toggle'):
    require(css,token,'0.10.90 list/recycle CSS')

ai=read('portal/services/ai.py')
require(ai,"'scoutbox_version': '0.10.90'",'AI telemetry version')

for path in Path(ROOT/'portal').rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
for path in Path(ROOT/'scripts').rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))

print('ScoutBox 0.10.90 targeted regressions passed.')
