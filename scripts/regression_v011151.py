from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.151'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.151'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.151'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.151'
assert 'The release following 0.11.151 is 0.11.152' in read('RELEASE_POLICY.md')

markets=read('portal/services/discovery_markets.py')
for needle in (
    "'Azerbaijani':'az'", "'Bosnian':'bs'", "'Burmese':'my'", "'Kazakh':'kk'",
    "'Khmer':'km'", "'Lao':'lo'", "'Mongolian':'mn'", "'Nepali':'ne'",
    "'Sinhala':'si'", "'Tamil':'ta'", "'Uzbek':'uz'",
):
    assert needle in markets, needle
assert "re.fullmatch(r'[a-zA-Z]{2,3}',value)" in markets
assert "low[:12]" not in markets

views=read('portal/views.py')
assert 'query_language_code(explicit_raw)' in views
assert "Q(metadata__query_language__iexact=label)" in views
assert "language_code=(query_language_code(language_raw) or query_language_code(language_label))" in views
assert "row.query_language_code=(query_language_code(language_raw) or query_language_code(row.query_language_label))" in views

# Exercise the standalone language helpers without importing Django.
module=ast.parse(markets)
selected=[]
for node in module.body:
    if isinstance(node,(ast.Assign,ast.FunctionDef)):
        names=[]
        if isinstance(node,ast.Assign):
            names=[t.id for t in node.targets if isinstance(t,ast.Name)]
        else:
            names=[node.name]
        if any(n in {'QUERY_LANGUAGE_CODE_BY_NAME','QUERY_LANGUAGE_NAME_BY_CODE','query_language_code','query_language_label'} for n in names):
            selected.append(node)
ns={'re':__import__('re')}
exec(compile(ast.Module(body=selected,type_ignores=[]),'<language-helper-test>','exec'),ns)
expected={
    'Azerbaijani':'az','Bosnian':'bs','Burmese':'my','Kazakh':'kk','Khmer':'km','Lao':'lo',
    'Mongolian':'mn','Nepali':'ne','Sinhala':'si','Tamil':'ta','Uzbek':'uz',
    'English':'en','French':'fr','German':'de','Chinese':'zh',
}
for label,code in expected.items():
    assert ns['query_language_code'](label)==code,(label,ns['query_language_code'](label))
    assert ns['query_language_label'](code)==label,(code,ns['query_language_label'](code))
assert ns['query_language_code']('azerbaijani')=='az'
assert ns['query_language_code']('khmer')=='km'
assert ns['query_language_code']('NotALanguageName')==''

migration=read('portal/migrations/0223_v011151_query_language_code_normalization.py')
assert "version='0.11.151'" in migration
assert "('portal','0222_v011150_diagnostic_export_period_alignment')" in migration
assert 'historical_usage_metrics_rewritten' in migration
assert 'ScoutBox/0.11.151' in read('portal/services/search.py')

print('ScoutBox 0.11.151 targeted regression checks passed')
