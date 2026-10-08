from pathlib import Path
import ast
import builtins
import symtable

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.118'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.118'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.118'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.118'
assert (root / 'docs/RELEASE_NOTES_0.11.118.md').exists()

tasks_text = read('portal/tasks.py')
tree = ast.parse(tasks_text)

# The regression that caused the runtime failure: the helpers referenced
# concurrent.futures but portal.tasks did not bind the name ``concurrent``.
assert 'import concurrent.futures' in tasks_text

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

# Targeted symbol sanity check for the three helpers and their nested workers.
# symtable distinguishes globals from locally imported/assigned names, so this
# catches missing module-level imports such as the original ``concurrent`` bug.
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

mig = read('portal/migrations/0190_v011118_parallel_reevaluation_import.py')
assert "version='0.11.118'" in mig
assert '0189_v011117_remove_provider_query_hard_cap' in mig
ast.parse(mig)
print('ScoutBox 0.11.118 targeted regression checks passed')
