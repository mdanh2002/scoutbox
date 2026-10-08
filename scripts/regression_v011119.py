from pathlib import Path
import ast
import builtins
import symtable

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.119'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.119'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.119'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.119'
assert (root / 'docs/RELEASE_NOTES_0.11.119.md').exists()

tasks_text = read('portal/tasks.py')
tree = ast.parse(tasks_text)

# Gemini parallel manual re-evaluation must retain the compatibility retry that
# _run_manual_filter performs when the first grounded response has no visible text.
assert 'def _parallel_manual_filter_empty_response_budget(provider):' in tasks_text
assert "return 2 if str(provider or '').strip().lower() == 'gemini' else 1" in tasks_text
assert tasks_text.count('empty_response_budget=_parallel_manual_filter_empty_response_budget(provider)') == 3

parallel_names = {
    '_parallel_opportunity_filter',
    '_parallel_hidden_lead_filter',
    '_parallel_contact_filter',
}
funcs = {
    node.name: node for node in tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in parallel_names
}
assert set(funcs) == parallel_names
for name, node in funcs.items():
    source = ast.get_source_segment(tasks_text, node) or ''
    assert 'concurrent.futures.ThreadPoolExecutor' in source, name
    assert 'concurrent.futures.as_completed' in source, name
    assert 'empty_response_budget=_parallel_manual_filter_empty_response_budget(provider)' in source, name
    assert 'empty_response_budget=1' not in source, name

# Keep the 0.11.118 missing-import guard as part of this regression.
assert 'import concurrent.futures' in tasks_text
module_bound = set(dir(builtins))
for node in tree.body:
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_bound.add(alias.asname or alias.name.split('.')[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            if alias.name != '*':
                module_bound.add(alias.asname or alias.name)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        module_bound.add(node.name)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            for sub in ast.walk(target):
                if isinstance(sub, ast.Name):
                    module_bound.add(sub.id)

st = symtable.symtable(tasks_text, 'portal/tasks.py', 'exec')
by_name = {child.get_name(): child for child in st.get_children()}

def referenced_globals(table):
    names = {sym.get_name() for sym in table.get_symbols() if sym.is_referenced() and sym.is_global()}
    for child in table.get_children():
        names.update(referenced_globals(child))
    return names

for name in parallel_names:
    unresolved = sorted(referenced_globals(by_name[name]) - module_bound)
    assert not unresolved, f'{name} unresolved global names: {unresolved}'

# The retry implementation itself must still be present and must switch Gemini
# to minimal thinking / no forced JSON MIME on the second grounded attempt.
filter_text = read('portal/services/opportunity_filter.py')
assert "if provider!='gemini' or int(empty_response_budget or 0)<=1:" in filter_text
assert "'_manual_empty_retry_minimal':True" in filter_text
assert "'_manual_disable_json_mime':True" in filter_text

mig = read('portal/migrations/0191_v011119_gemini_parallel_reevaluation_retry.py')
assert "version='0.11.119'" in mig
assert '0190_v011118_parallel_reevaluation_import' in mig
ast.parse(mig)
print('ScoutBox 0.11.119 targeted regression checks passed')
