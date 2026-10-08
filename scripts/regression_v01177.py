from pathlib import Path
from types import SimpleNamespace
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from portal.services.discovery_markets import MARKET_BY_CODE, market_plan, multilingual_assignments


def read(name): return (root/name).read_text(encoding='utf-8')


assert read('VERSION').strip()=='0.11.77'
sources=read('templates/portal/sources.html')
base=read('templates/portal/base.html')
css=read('portal/static/portal/app.css')
views=read('portal/views.py')
discovery=read('portal/services/discovery.py')
cloud=read('portal/services/cloud_discovery.py')

guidance=(
    'English remains the primary discovery language. Multilingual exploration adds a small number '
    'of local-language searches for enabled markets and selected languages, keeping only results '
    'that meet the same or stricter relevance and quality checks.'
)
assert guidance in sources
assert sources.index('Market coverage') < sources.index('Exploration strength') < sources.index('Additional languages')
assert 'title="Even rotates equally.' not in sources
assert 'aria-describedby="market-coverage-help"' in sources
assert 'aria-describedby="exploration-strength-help"' in sources

assert "'ATS / hosted career pages':'Hosted career pages'" in views
assert "'Developer / engineering communities':'Developer communities'" in views
assert "'Excluded / low-value marketplaces':'Low-value marketplaces'" in views
assert "'Singapore / APAC':'Other Sources'" in views
assert "'Startup / technology jobs':'Other Sources'" in views
assert "category_items.sort(key=lambda item:str(item.name or '').casefold())" in views
assert 'data-search="{{category}} {{s.source_category_search}} {{s.name}}"' in sources

assert '#source-list .source-inline{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))' in css
assert '@media(max-width:1200px){#source-list .source-inline{grid-template-columns:repeat(3,minmax(0,1fr))' in css
assert '@media(max-width:620px){#source-list .source-inline{grid-template-columns:1fr}' in css
assert '#source-list .source-direct-badge{display:none!important}' in css
assert 'source-direct-badge' in sources and 'aria-hidden="true">Direct</span>' in sources
assert '#source-markets .discovery-market-settings-grid{display:grid;grid-template-columns:minmax(0,1fr)' in css
assert 'max-height:176px' in css and 'width:300px' in css
assert 'function positionPanel()' in base
assert "panel.style.left=left+'px'" in base and "panel.style.width=width+'px'" in base

settings=SimpleNamespace(
    discovery_markets=['worldwide','us','ca','gb','de'],discovery_market_strategy='adaptive',
    multilingual_exploration_enabled=True,multilingual_exploration_strength='balanced',
    multilingual_languages=['German','Spanish'],
)
fallback=market_plan(settings,campaign_id=7,rotation_offset=3,evidence={})
assert fallback['effective_strategy']=='even' and 'Adaptive' in fallback['fallback']
assignments=multilingual_assignments(settings,[MARKET_BY_CODE[x] for x in settings.discovery_markets])
assert len(assignments)==2
assert [x['language'] for x in assignments]==['German','Spanish']
assert all(x['source']=='additional' and x['market'].code=='worldwide' for x in assignments)

for token in ['_translate_multilingual_page','multilingual_translation_failed','multilingual_executed','market_coverage']:
    assert token in discovery
for token in ['multilingual_assignments','multilingual supplemental pass','market_coverage','multilingual_exploration']:
    assert token in cloud

print('ScoutBox 0.11.77 regression checks passed')
