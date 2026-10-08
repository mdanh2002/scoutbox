#!/usr/bin/env python3
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.107'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.107'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.107'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.107'
assert (R/'docs'/'RELEASE_NOTES_0.10.107.md').is_file()

focus=t('portal/services/focus.py')
req(focus,'Campaign names are weak hints only inside the Local AI prompt', 'campaign is not deterministic focus source')
forbid(focus,'def _campaign_focus_choice', 'campaign-dominance focus assignment removed')
forbid(focus,'similarity>=0.055', 'weak peer fallback removed')
req(focus,'def _distinctive_label_tokens', 'distinctive label support guard present')
req(focus,'_record_supports_focus_label(record,peer_label', 'peer label must be supported by row content')
req(focus,"'source':'peer_similarity'", 'focus assignment provenance source')
req(focus,"'release':'0.10.107'", 'focus provenance release stamp')
req(focus,'counts=defaultdict(int)', 'blank and explicit Unclassified options merged')
req(focus,"return {'due':False", 'automatic full Focus rebuild disabled')

tasks=t('portal/tasks.py')
req(tasks,"ps.focus_taxonomy_version='0.10.107'", 'tasks stamp 0.10.107 focus state')
req(tasks,"'release':'0.10.107','snapshot':snap", 'blank backfill metadata is 0.10.107')

mig106=t('portal/migrations/0126_v010106_focus_ui_cleanup.py')
forbid(mig106,'origin_campaign_id', '0.10.106 migration no longer bulk-fills by campaign dominance')
forbid(mig106,'Count(', '0.10.106 migration no longer counts campaign dominant focus')

mig=t('portal/migrations/0127_v010107_focus_repair.py')
req(mig,"campaign_dominance_assignment_disabled", 'upgrade records campaign dominance disabled')
req(mig,"v010107_dominance_repair", 'upgrade records dominance repair summary')
req(mig,"status='stopped',message='Superseded by ScoutBox 0.10.107 content-only Focus repair'", 'upgrade stops old focus backfill jobs')
req(mig,"def supports(row,label):", 'migration clears unsupported dominant labels by row content')
req(mig,"'previous_focus':str(previous", 'migration writes focus repair provenance')
forbid(mig,'requests.', 'migration must not call network')

css=t('portal/static/portal/app.css')
req(css,'.discovery-activity-title', 'Discovery Activity title spinner styling')
req(css,'.discovery-activity-controls #discovery-activity-loading{display:none!important}', 'spinner no longer belongs in toolbar')

dashboard=t('templates/portal/dashboard.html')
req(dashboard,'<h3 class="discovery-activity-title">Discovery Activity <span id="discovery-activity-loading"', 'spinner sits beside heading text')
if dashboard.index('id="discovery-activity-loading"') > dashboard.index('id="activity-ranges"'):
    raise SystemExit('FAIL spinner is still after range toolbar')
req(dashboard,'refresh(true)', 'manual range changes show spinner')

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py'))+list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.107 targeted regressions passed.')
