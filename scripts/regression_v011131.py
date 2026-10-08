from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.131'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.131'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.131'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.131'
assert (root/'docs/RELEASE_NOTES_0.11.131.md').exists()

profile=read('templates/portal/profile.html')
assert 'id="cv-table"' in profile
assert 'id="cover-table"' in profile
assert 'id="profile-autopopulate-btn"' in profile
assert 'class="btn profile-autopopulate-action"' in profile
assert 'Build Resume concepts and likely roles from every uploaded Resume' not in profile
assert 'Autopopulate Candidate Profile from all uploaded Resumes?' in profile
assert 'binary-confirm-card' in profile

css=read('portal/static/portal/app.css')
# 0.11.130 UI behavior remains intact.
assert '/* 0.11.130 — compact binary confirmations and Candidate Profile action polish. */' in css
assert '.profile-autopopulate-action{' in css
assert '.portal-confirm-card,.binary-confirm-card{width:min(520px,calc(100vw - 32px))!important' in css
# 0.11.131 Cover Letter geometry mirrors Resume boundaries.
assert '/* 0.11.131 — align Cover Letter columns with the Resume table geometry. */' in css
assert '#cover-table.profile-assets-table{min-width:900px!important;table-layout:fixed!important}' in css
assert '#cover-table th:nth-child(1),#cover-table td:nth-child(1){width:calc(100% - 577px)!important' in css
assert '#cover-table th:nth-child(2),#cover-table td:nth-child(2){width:392px!important;min-width:392px!important' in css
assert '#cover-table th:nth-child(3),#cover-table td:nth-child(3){width:auto!important;min-width:0!important;text-align:right!important' in css
assert '#cover-table td:nth-child(3)>form{display:flex;justify-content:flex-end;width:100%;margin:0}' in css
assert '#cover-table td:nth-child(1)>a{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' in css
# Resume reference geometry used by the Cover Letter alignment must remain unchanged.
assert '#cv-table th:nth-child(2),#cv-table td:nth-child(2){width:172px!important;min-width:172px!important' in css
assert '#cv-table th:nth-child(3),#cv-table td:nth-child(3){width:220px!important;min-width:220px!important' in css
assert '#cv-table th:nth-child(4),#cv-table td:nth-child(4){width:185px!important;min-width:185px!important' in css

# 0.11.129 Candidate Profile behavior remains intact.
tasks=read('portal/tasks.py')
assert "scope['profile_autopopulate_version']='0.11.129'" in tasks
assert 'def candidate_profile_autopopulate_job' in tasks
assert "'merge_strategy':'round_robin_per_resume'" in tasks
qp=read('portal/services/queryplanner.py')
assert 'PROFILE_CONCEPT_LIMIT = 160' in qp
assert 'PROFILE_ROLE_LIMIT = 80' in qp

# 0.11.128 re-evaluation evidence remains intact.
of=read('portal/services/opportunity_filter.py')
assert "'active_resumes':[" in of
assert "'resume_grounded_concepts':grounded_resume_concepts(cv_texts)" in of

mig=read('portal/migrations/0203_v011131_cover_letter_table_alignment.py')
assert "version='0.11.131'" in mig
assert "dependencies = [('portal', '0202_v011130_confirm_dialog_polish')]" in mig

print('ScoutBox 0.11.131 targeted regression checks passed')
