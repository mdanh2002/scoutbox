from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.152'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.152'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.152'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.152'
assert 'The release following 0.11.152 is 0.11.153' in read('RELEASE_POLICY.md')
assert "PORTAL_LAST_MODIFIED = '2026-10-01 12:27:00'" in read('opportunity_portal/settings.py')

markets=read('portal/services/discovery_markets.py')
assert 'def query_language_identity' in markets
module=ast.parse(markets)
selected=[]
for node in module.body:
    if isinstance(node,(ast.Assign,ast.FunctionDef)):
        names=[]
        if isinstance(node,ast.Assign):
            names=[t.id for t in node.targets if isinstance(t,ast.Name)]
        else:
            names=[node.name]
        if any(n in {'QUERY_LANGUAGE_CODE_BY_NAME','QUERY_LANGUAGE_NAME_BY_CODE','query_language_code','query_language_label','query_language_identity'} for n in names):
            selected.append(node)
ns={'re':__import__('re')}
exec(compile(ast.Module(body=selected,type_ignores=[]),'<language-facet-test>','exec'),ns)
identity=ns['query_language_identity']
assert identity('en','English','')==('known','en','English')
assert identity('Azerbaijani','','')==('known','az','Azerbaijani')
assert identity('','','French')==('known','fr','French')
assert identity('Klingon','','')==('unknown','','Unknown')
assert identity('','','')==('unrecorded','','')

views=read('portal/views.py')
assert "query_language_unrecorded_total=0" in views
assert "language_name_by_code=dict(QUERY_LANGUAGE_NAME_BY_CODE)" in views
assert "query_language_unrecorded_total+=count" in views
assert "'code':'?' if key=='__unknown__' else key.upper()" in views
assert "return _query_language_explicit_q() & ~_query_language_known_q()" in views
assert "query_language_unrecorded_total=query_language_unrecorded_total" in views
assert "'Unknown (?)' if language_state=='unknown' else 'Not recorded'" in views

html=read('templates/portal/search_log.html')
assert '<span class="search-filter-option-code">{{item.code|default:\'?\'}}</span>' in html

migration=read('portal/migrations/0224_v011152_query_language_unknown_faceting.py')
assert "version='0.11.152'" in migration
assert "('portal','0223_v011151_query_language_code_normalization')" in migration
assert 'historical_usage_metrics_rewritten' in migration
assert 'ScoutBox/0.11.152' in read('portal/services/search.py')
assert 'ScoutBox/0.11.152' in read('portal/services/fresh_sources.py')

print('ScoutBox 0.11.152 targeted regression checks passed')
