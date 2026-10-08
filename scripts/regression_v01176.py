from pathlib import Path
from types import SimpleNamespace
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from portal.services.discovery_markets import (
    MARKET_BY_CODE, MARKETS, market_plan, multilingual_assignments,
)


def read(name): return (root/name).read_text(encoding='utf-8')


assert read('VERSION').strip()=='0.11.76'
sources=read('templates/portal/sources.html')
css=read('portal/static/portal/app.css')
base=read('templates/portal/base.html')
views=read('portal/views.py')
discovery=read('portal/services/discovery.py')
cloud=read('portal/services/cloud_discovery.py')

guidance='English remains the primary discovery language. When multilingual exploration is enabled'
assert guidance in sources
assert sources.index(guidance) < sources.index('name="multilingual_exploration_enabled"') < sources.index('placeholder="Search markets…"')
assert 'data-searchable-token="true"' in sources and 'list="discovery-language-options"' not in sources
assert 'source-choice-content' in sources
assert '#source-list .source-inline{display:grid!important' in css
assert '#source-markets [data-discovery-market][hidden]{display:none!important}' in css
assert '.token-options-popover[hidden],.token-option[hidden]{display:none!important}' in css
assert 'function initTokenInputs()' in base and "input.removeAttribute('list')" in base
assert "sorted(MARKETS,key=lambda m:(m.code=='worldwide',m.name.casefold()))" in views

settings=SimpleNamespace(
    discovery_markets=['us','ca','gb','de'],discovery_market_strategy='even',
    multilingual_exploration_enabled=True,multilingual_exploration_strength='balanced',
    multilingual_languages=['German','Spanish'],
)
evidence={
    'us':{'attempts':10,'pages':10,'errors':4,'retained':0},
    'ca':{'attempts':10,'pages':20,'errors':0,'retained':1},
    'gb':{'attempts':10,'pages':12,'errors':1,'retained':1},
    'de':{'attempts':10,'pages':30,'errors':0,'retained':8},
}
even=market_plan(settings,campaign_id=7,rotation_offset=3,evidence=evidence)
settings.discovery_market_strategy='balanced'; balanced=market_plan(settings,campaign_id=7,rotation_offset=3,evidence=evidence)
settings.discovery_market_strategy='adaptive'; adaptive=market_plan(settings,campaign_id=7,rotation_offset=3,evidence=evidence)
assert even['effective_strategy']=='even'
assert balanced['effective_strategy']=='balanced'
assert adaptive['effective_strategy']=='adaptive'
assert len({tuple(even['ordered_codes']),tuple(balanced['ordered_codes']),tuple(adaptive['ordered_codes'])})>=2
assert even['ordered_codes'][0]==balanced['ordered_codes'][0]==adaptive['ordered_codes'][0]

settings.discovery_market_strategy='adaptive'
fallback=market_plan(settings,campaign_id=7,rotation_offset=3,evidence={})
assert fallback['effective_strategy']=='even' and 'Adaptive' in fallback['fallback'] and 'Balanced' in fallback['fallback']

assignments=multilingual_assignments(settings,[MARKET_BY_CODE[x] for x in settings.discovery_markets],rotation_offset=0)
assert len(assignments)==2
assert [x['language'] for x in assignments]==['German','Spanish']
assert all(x['source']=='additional' for x in assignments)
worldwide_assignments=multilingual_assignments(settings,[MARKET_BY_CODE['de'],MARKET_BY_CODE['worldwide']],rotation_offset=0)
assert all(x['market'].code=='worldwide' for x in worldwide_assignments)
settings.multilingual_exploration_strength='low'
first={multilingual_assignments(settings,[MARKET_BY_CODE[x] for x in settings.discovery_markets],rotation_offset=i)[0]['language'] for i in range(2)}
assert first=={'German','Spanish'}
settings.multilingual_exploration_enabled=False
assert multilingual_assignments(settings,[MARKET_BY_CODE['de']])==[]

for token in ['_translate_multilingual_page','multilingual_translation_failed','multilingual_executed','market_coverage']:
    assert token in discovery
for token in ['multilingual_assignments','multilingual supplemental pass','market_coverage','multilingual_exploration']:
    assert token in cloud

migration=read('portal/migrations/0155_v01176_worldwide_job_sources.py')
for token in ['StepStone Germany','France Travail','InfoJobs Spain','Nationale Vacaturebank','Cliclavoro Italy','Pracuj.pl','Jobs.cz','FINN Jobs','Daijob','JobKorea','Vagas.com.br','OCCMundial']:
    assert token in migration

names=[m.name for m in MARKETS if m.code!='worldwide']
assert len(MARKETS)>=30 and len(names)==len(set(names))
print('ScoutBox 0.11.76 regression checks passed')
