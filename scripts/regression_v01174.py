from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(name): return (root/name).read_text(encoding='utf-8')
assert read('VERSION').strip()=='0.11.74'
sources=read('templates/portal/sources.html')
assert 'Discovery Markets' in sources
assert 'Preferred Search Engines' not in sources
assert 'multilingual_exploration_enabled' in sources
assert 'name="discovery_market"' in sources
models=read('portal/models.py')
for field in ['discovery_markets','discovery_market_strategy','multilingual_exploration_enabled','multilingual_language_mode','multilingual_languages','multilingual_exploration_strength']:
    assert field in models
markets=read('portal/services/discovery_markets.py')
for token in ['Worldwide','Singapore','Malaysia','Hong Kong','United Arab Emirates','SEEK Australia','MyCareersFuture','JobsDB Hong Kong']:
    assert token in markets
search=read('portal/services/search.py')
assert 'Preferred Search Engines is retired' in search
query=read('portal/services/queryplanner.py')
assert 'Candidate Profile does not contain enough reliable role/skill evidence' in read('portal/services/discovery.py')
assert 'specialist software engineer' not in query.lower()
contacts=read('portal/static/portal/app.css')
assert '#contacts-table td:nth-child(3) .contact-link-cell>a' in contacts
assert 'overflow-wrap:anywhere' in contacts[contacts.index('#contacts-table td:nth-child(3) .contact-link-cell'):]
print('ScoutBox 0.11.74 regression checks passed')
