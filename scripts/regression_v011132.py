from pathlib import Path
import ast
import concurrent.futures
import json

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.132'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.132'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.132'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.132'
assert (root/'docs/RELEASE_NOTES_0.11.132.md').exists()

# 0.11.131 Candidate Profile table alignment remains intact.
css=read('portal/static/portal/app.css')
assert '/* 0.11.131 — align Cover Letter columns with the Resume table geometry. */' in css
assert '#cover-table.profile-assets-table{min-width:900px!important;table-layout:fixed!important}' in css

# Re-evaluation scope dialog has enough desktop width for History + four scope actions.
assert '.portal-choice-card{width:min(980px,calc(100vw - 32px))!important;max-width:min(980px,calc(100vw - 32px))!important}' in css
assert '.portal-choice-card{width:min(820px,96vw)!important;max-width:96vw!important}' in css
assert '.portal-choice-card{width:min(980px,96vw)!important;max-width:96vw!important}' in css
# Historical scope-width rules must not widen the compact confirmation modal by mistake.
assert '.portal-confirm-card{width:min(820px,96vw)!important' not in css
assert '.portal-confirm-card{width:min(980px,96vw)!important' not in css
assert '.portal-confirm-card,.binary-confirm-card{width:min(520px,calc(100vw - 32px))!important' in css

# Execute the two prompt-building paths without importing Django. Reaching the provider-call
# stub proves the prompt expression itself can be evaluated in both Local and Cloud modes.
of_source=read('portal/services/opportunity_filter.py')
of_tree=ast.parse(of_source)
for node in ast.walk(of_tree):
    assert not (isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.UAdd)), 'unexpected unary + in opportunity_filter.py'
fn_names={'classify_existing_opportunity','classify_existing_hidden_lead'}
fn_nodes=[n for n in of_tree.body if isinstance(n,ast.FunctionDef) and n.name in fn_names]
assert {n.name for n in fn_nodes}==fn_names
ns={
    'json':json,
    'CLOUD_FILTER_PROVIDERS':{'openai','gemini','openrouter'},
    'CANDIDATE_EVIDENCE_RULES':'Candidate evidence rules. ',
    '_manual_route':lambda provider,model:{'provider':provider or 'gemini','model':model or 'gemini-test'},
    'opportunity_evidence_text':lambda opp:('retained evidence '*40,'description'),
    'hidden_lead_evidence_text':lambda lead:('retained evidence '*40,'evidence'),
    '_clean_retained_opportunity_text':lambda *args,**kwargs:'clean retained evidence',
    '_cloud_policy_prompt':lambda *args,**kwargs:'Use current public evidence.',
    '_candidate_scope':lambda obj:{'skills':['python']},
}
class PromptCaptured(Exception): pass
captured=[]
def capture_provider_call(route,prompt,**kwargs):
    captured.append(prompt)
    raise PromptCaptured
ns['_run_manual_filter']=capture_provider_call
exec(compile(ast.fix_missing_locations(ast.Module(body=fn_nodes,type_ignores=[])),'<opportunity_filter_regression>','exec'),ns)
class Opp:
    pk=1; title='Engineer'; company='Acme'; target_url='https://example.test/job'; url=target_url
class Lead:
    pk=2; company='Acme'; target_url='https://example.test'; source_url=target_url
for internet_search in (False,True):
    for fn,obj in ((ns['classify_existing_opportunity'],Opp()),(ns['classify_existing_hidden_lead'],Lead())):
        try:
            fn(obj,provider='gemini',model='gemini-test',internet_search=internet_search,cloud_policy_prompt='policy')
        except PromptCaptured:
            pass
        else:
            raise AssertionError('manual re-evaluation prompt did not reach provider-call stub')
assert len(captured)==4
assert all('CANDIDATE SCOPE' in prompt for prompt in captured)
assert sum('CLOUD RE-EVALUATION INSTRUCTIONS:' in prompt for prompt in captured)==2

# Batch guardrails: bounded cloud submission, repeated-internal-error detection and an
# all-failed batch state that cannot be mislabeled as an ordinary completion.
tasks=read('portal/tasks.py')
assert 'MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD = 3' in tasks
assert 'def _fail_manual_filter_repeated_internal_error' in tasks
assert 'def _manual_filter_all_selected_failed' in tasks
assert 'def _bounded_parallel_futures' in tasks
assert tasks.count('_bounded_parallel_futures(pool,worker,ids,MANUAL_FILTER_CLOUD_PARALLELISM)')==3
assert 'futures={pool.submit(worker,i):i for i in ids}' not in tasks
assert tasks.count("'kind':'repeated_internal_error'")==1
assert tasks.count("'kind':'empty_response'")==1
assert tasks.count("'timed_out':0")>=6

tasks_tree=ast.parse(tasks)
helper_names={'_manual_filter_exception_result','_manual_filter_internal_failure_signature','_manual_filter_all_selected_failed','_bounded_parallel_futures'}
helper_nodes=[n for n in tasks_tree.body if isinstance(n,ast.FunctionDef) and n.name in helper_names]
assert {n.name for n in helper_nodes}==helper_names
helper_ns={
    'MANUAL_FILTER_INTERNAL_EXCEPTIONS':(TypeError,AttributeError,NameError,UnboundLocalError,ImportError,KeyError,IndexError,AssertionError,ZeroDivisionError),
    'concurrent':type('ConcurrentNamespace',(),{'futures':concurrent.futures}),
}
exec(compile(ast.fix_missing_locations(ast.Module(body=helper_nodes,type_ignores=[])),'<tasks_regression>','exec'),helper_ns)
result=helper_ns['_manual_filter_exception_result']({'id':1},TypeError("bad operand type for unary +: 'str'"))
assert result['internal_error'] is True
assert helper_ns['_manual_filter_internal_failure_signature'](result).startswith('TypeError: bad operand type for unary +')
assert helper_ns['_manual_filter_exception_result']({'id':1},RuntimeError('provider failure'))['internal_error'] is False
assert helper_ns['_manual_filter_all_selected_failed']({'processed':3,'failed':3},3) is True
assert helper_ns['_manual_filter_all_selected_failed']({'processed':3,'failed':2},3) is False
class FakePool:
    def __init__(self): self.submits=0
    def submit(self,fn,item):
        self.submits+=1
        future=concurrent.futures.Future(); future.set_result(fn(item)); return future
pool=FakePool()
gen=helper_ns['_bounded_parallel_futures'](pool,lambda value:value*2,range(10),3)
future,item=next(gen)
assert pool.submits==3 and future.result()==item*2
remaining=list(gen)
assert pool.submits==10 and len(remaining)==9

mig=read('portal/migrations/0204_v011132_reevaluation_reliability.py')
assert "version='0.11.132'" in mig
assert "dependencies = [('portal', '0203_v011131_cover_letter_table_alignment')]" in mig

print('ScoutBox 0.11.132 targeted regression checks passed')
