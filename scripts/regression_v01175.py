from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(name): return (root/name).read_text(encoding='utf-8')
assert read('VERSION').strip()=='0.11.75'
sources=read('templates/portal/sources.html')
assert 'Discovery Markets control where ScoutBox looks.' not in sources
assert '<h4>Multilingual exploration</h4>' not in sources
assert 'Auto from enabled markets' not in sources
assert 'Used only when Languages is Custom' not in sources
assert 'Additional languages' in sources
assert 'discovery-language-options' in sources
assert 'English remains primary; foreign-language results are retained only when strongly relevant.' in sources
assert sources.index('Search selected markets in local languages where useful') < sources.index('Save Discovery Markets')
assert '{{m.languages}}' not in sources
markets=read('portal/services/discovery_markets.py')
for token in ['DEFAULT_ADDITIONAL_LANGUAGES', "('French','🇫🇷')", "('German','🇩🇪')", "('Spanish','🇪🇸')"]:
    assert token in markets
assert 'for language in (getattr(settings_obj,\'multilingual_languages\'' in markets
views=read('portal/views.py')
assert "ps.multilingual_language_mode='auto'" in views
css=read('portal/static/portal/app.css')
assert '.discovery-market-settings-grid' in css
assert '.discovery-market-additional' in css
print('ScoutBox 0.11.75 regression checks passed')
