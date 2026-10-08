from pathlib import Path
import ast
import re

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.129'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.129'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.129'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.129'
assert (root/'docs/RELEASE_NOTES_0.11.129.md').exists()

qp=read('portal/services/queryplanner.py')
assert 'PROFILE_CONCEPT_LIMIT = 160' in qp
assert 'PROFILE_ROLE_LIMIT = 80' in qp
assert 'def grounded_resume_concepts' in qp
assert 'def grounded_resume_roles' in qp
assert '# Candidate Profile values are additive/curated signals, not a whitelist' in qp

tasks=read('portal/tasks.py')
start=tasks.index('def _profile_autopopulate_key')
end=tasks.index('@shared_task(bind=True)\ndef campaign_templates_job', start)
auto=tasks[start:end]
for expected in (
    'def _profile_round_robin_unique',
    'def candidate_profile_autopopulate_job',
    'docs=extract_active_cv_texts()',
    'for index,doc in enumerate(docs,1):',
    'grounded_resume_concepts([text],PROFILE_CONCEPT_LIMIT)',
    'grounded_resume_roles([text],PROFILE_ROLE_LIMIT)',
    "_profile_concept_supported(term,text)",
    "limits_override={'max_input_tokens':0,'max_output_tokens':8000}",
    "job.status=='stopped'",
    "AI extraction unavailable; deterministic Resume evidence used.",
    "scope['cv_concepts']=concepts[:PROFILE_CONCEPT_LIMIT]",
    "scope['likely_roles']=roles[:PROFILE_ROLE_LIMIT]",
    "scope['profile_autopopulate_version']='0.11.129'",
    "'duplicates_removed':True",
    "'merge_strategy':'round_robin_per_resume'",
    "with transaction.atomic():",
    "'profile_committed':True",
): assert expected in auto, expected
assert 'docs[:' not in auto
assert auto.index('for index,doc in enumerate(docs,1):') < auto.index("scope['cv_concepts']=concepts[:PROFILE_CONCEPT_LIMIT]")

# Execute only the pure de-duplication helpers so their actual behavior is regression-tested
# without importing Django/Celery in the static release verifier.
tree=ast.parse(tasks)
selected=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in {'_profile_autopopulate_key','_profile_round_robin_unique'}]
module=ast.Module(body=selected,type_ignores=[])
ns={'re':re}
exec(compile(module,'portal/tasks.py','exec'),ns)
merge=ns['_profile_round_robin_unique']
values=merge([
    ['BACnet / Modbus','C++','Linux','Python'],
    [' bacnet/modbus ','Modbus','PostgreSQL','Java'],
    ['C++','QEMU / KVM','STM32'],
],6)
keys=[ns['_profile_autopopulate_key'](x) for x in values]
assert len(values)==6 and len(keys)==len(set(keys)), values
assert values[0]=='BACnet / Modbus'
assert 'Modbus' in values and 'C++' in values
# Round-robin fairness: each Resume contributes before the first Resume can fill the cap.
short=merge([['a1','a2','a3'],['b1','b2'],['c1']],3)
assert short==['a1','b1','c1'], short

views=read('portal/views.py')
assert 'candidate_profile_autopopulate_job' in views
assert 'def profile_autopopulate_async' in views
assert "label='Autopopulate Candidate Profile'" in views
assert "'tool':'candidate_profile_autopopulate'" in views
assert "if tool=='candidate_profile_autopopulate': kind_label='Candidate Profile'" in views
assert "Another Candidate Profile rebuild is already running" in views

urls=read('portal/urls.py')
assert "path('profile/autopopulate/',views.profile_autopopulate_async,name='profile_autopopulate_async')" in urls

profile=read('templates/portal/profile.html')
assert 'id="profile-autopopulate-btn"' in profile
assert 'Autopopulate Candidate Profile' in profile
assert profile.index('Auto-create Campaign Templates') < profile.index('id="profile-autopopulate-btn"')
assert 'id="profile-autopopulate-notice"' in profile
assert 'Open Dashboard / Stop' in profile
assert '{% url "profile_autopopulate_async" %}' in profile
assert 'Current Resume concepts and likely roles will be replaced' in profile
assert 'Existing Candidate Profile terms were left unchanged.' in profile
assert 'id="profile-autopopulate-notice-title"' in profile
assert 'id="profile-autopopulate-notice-action"' in profile
assert 'Reload Candidate Profile' in profile
assert 'profileLocked' in profile

css=read('portal/static/portal/app.css')
assert '/* 0.11.129 — background Candidate Profile autopopulation. */' in css
assert '.profile-autopopulate-notice[hidden]' in css

# 0.11.128 evidence propagation must remain present.
of=read('portal/services/opportunity_filter.py')
assert "'active_resumes':[" in of
assert "'resume_grounded_concepts':grounded_resume_concepts(cv_texts)" in of
assert "MANUAL_REEVALUATION_LIMITS = {'max_input_tokens': 0, 'max_output_tokens': 4000}" in of

diag=views
assert "'manual_reevaluation_payload_exported':True" in diag
assert "'raw_prompt_output_exported':'manual_reevaluations_only'" in diag

mig=read('portal/migrations/0201_v011129_candidate_profile_autopopulate.py')
assert "version='0.11.129'" in mig
assert "dependencies = [('portal', '0200_v011128_resume_grounded_reevaluation')]" in mig

print('ScoutBox 0.11.129 targeted regression checks passed')
