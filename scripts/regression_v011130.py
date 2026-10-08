from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.130'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.130'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.130'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.130'
assert (root/'docs/RELEASE_NOTES_0.11.130.md').exists()

profile=read('templates/portal/profile.html')
assert 'id="profile-autopopulate-btn"' in profile
assert 'class="btn profile-autopopulate-action"' in profile
assert 'Build Resume concepts and likely roles from every uploaded Resume' not in profile
assert 'Autopopulate Candidate Profile from all uploaded Resumes?' in profile
assert 'Current Resume concepts and likely roles will be replaced.' in profile
assert 'binary-confirm-card' in profile
assert 'id="bulk-resume-template-modal"' in profile
assert 'id="asset-delete-modal"' in profile

css=read('portal/static/portal/app.css')
assert '/* 0.11.130 — compact binary confirmations and Candidate Profile action polish. */' in css
assert '.profile-autopopulate-action{' in css
assert '.portal-confirm-card,.binary-confirm-card{width:min(520px,calc(100vw - 32px))!important' in css
assert '@media(max-width:560px)' in css

base=read('templates/portal/base.html')
assert 'id="portal-confirm-modal"' in base and 'portal-confirm-card' in base
assert 'id="portal-choice-modal"' in base and 'portal-choice-card' in base
assert 'id="portal-choice-modal"' in base and 'portal-choice-modal" hidden' in base
# Re-evaluation configuration dialogs remain their existing specialist dialogs.
for rel, marker in (
    ('templates/portal/opportunities.html','manual-filter-modal-card manual-filter-cloud-modal-card'),
    ('templates/portal/cold_contact.html','manual-filter-modal-card manual-filter-cloud-modal-card'),
    ('templates/portal/contacts.html','manual-filter-modal-card'),
):
    text=read(rel)
    assert marker in text
    # Do not opt specialist re-evaluation dialogs into binary sizing.
    segment=text[text.index('Re-evaluate'):]
    assert 'binary-confirm-card' not in segment[:2500]

assert 'binary-confirm-card' in read('templates/portal/blacklist.html')
assert 'binary-confirm-card' in read('templates/portal/recycle_bin.html')
# Dialogs with typed confirmation fields are intentionally untouched.
settings=read('templates/portal/settings.html')
assert 'Type RECOVER' in settings and 'Type CLEAR' in settings and 'Type RESET' in settings
assert 'binary-confirm-card' not in settings

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

mig=read('portal/migrations/0202_v011130_confirm_dialog_polish.py')
assert "version='0.11.130'" in mig
assert "dependencies = [('portal', '0201_v011129_candidate_profile_autopopulate')]" in mig

print('ScoutBox 0.11.130 targeted regression checks passed')
