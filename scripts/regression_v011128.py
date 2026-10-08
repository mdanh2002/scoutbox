from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.128'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.128'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.128'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.128'
assert (root/'docs/RELEASE_NOTES_0.11.128.md').exists()

qp=read('portal/services/queryplanner.py')
assert 'PROFILE_CONCEPT_LIMIT = 160' in qp
assert 'PROFILE_ROLE_LIMIT = 80' in qp
assert 'def _profile_concept_supported' in qp
assert 'def grounded_resume_concepts' in qp
assert 'def grounded_resume_roles' in qp
assert "'BACnet', 'BACnet/IP', 'Modbus', 'KNX', 'OPC-UA', 'DNP3'" in qp
assert "# Candidate Profile values are additive/curated signals, not a whitelist" in qp
assert 'Keep literal Resume technologies as first-class concepts' in qp
assert "skills = []\n" not in qp[qp.index("if use_saved_overrides and 'cv_concepts'"):qp.index("# Preserve diversity", qp.index("if use_saved_overrides and 'cv_concepts'"))]

of=read('portal/services/opportunity_filter.py')
for expected in (
    "'cv_concepts': list(scope.get('cv_concepts') or [])",
    "'likely_roles': list(scope.get('likely_roles')",
    "'resume_grounded_concepts':grounded_resume_concepts(cv_texts)",
    "'resume_grounded_roles':grounded_resume_roles(cv_texts)",
    "'active_resumes':[",
    "'text':str(d.get('text') or '')",
    "'campaign_context':_record_campaign_context(record)",
    "MANUAL_REEVALUATION_LIMITS = {'max_input_tokens': 0, 'max_output_tokens': 4000}",
    "CANDIDATE_EVIDENCE_RULES",
    "'label':'Manual opportunity re-evaluation'",
    "'label':'Manual Hidden Lead re-evaluation'",
    "'label':'Manual Address Book re-evaluation'",
):
    assert expected in of, expected

views=read('portal/views.py')
assert "'format':'scoutbox-diagnostic','format_version':6" in views
assert 'def _diagnostic_candidate_context' in views
assert "'active_resumes':[" in views
assert "'parsed_text':_diagnostic_scrub(d.get('text') or ''" in views
assert "'manual_reevaluation_payload_exported':True" in views
assert "'raw_prompt_output_exported':'manual_reevaluations_only'" in views
assert "subject_label__istartswith='Manual '" in views
assert "subject_label__icontains='re-evaluation'" in views
assert 'PROFILE_CONCEPT_LIMIT' in views and 'PROFILE_ROLE_LIMIT' in views

profile_html=read('templates/portal/profile.html')
assert 'data-max-items="{{profile_concept_limit}}"' in profile_html
assert 'data-max-items="{{profile_role_limit}}"' in profile_html
base=read('templates/portal/base.html')
assert "box.dataset.maxLabel||'items'" in base

seed=read('portal/management/commands/seed_defaults.py')
assert "terms_release='0.11.128'" in seed
assert "portal.tasks.candidate_profile_defaults_job" in seed
assert "profile_terms_version" in read('portal/tasks.py')
tasks=read('portal/tasks.py')
assert "limits_override={'max_input_tokens':0,'max_output_tokens':8000}" in tasks

mig=read('portal/migrations/0200_v011128_resume_grounded_reevaluation.py')
assert "version='0.11.128'" in mig
assert "dependencies = [('portal', '0199_v011127_reevaluation_xlsx_layout')]" in mig

print('ScoutBox 0.11.128 targeted regression checks passed')
