"""ScoutBox 0.11.2 regression checks for Opportunity location-field repair."""
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from portal.services.location_values import record_location_items, location_labels, legacy_location_text, parse_location_items

# Old bad row shape: stale expanded legacy country value should not win over role_location.
row = SimpleNamespace(
    role_location='Remote from US',
    country='Albania, Andorra, Austria, Belarus, Belgium',
    locations=[
        {'label':'Albania','kind':'country'},
        {'label':'Andorra','kind':'country'},
        {'label':'Austria','kind':'country'},
        {'label':'Belarus','kind':'country'},
    ],
    remote_text='Fully remote',
)
labels = location_labels(record_location_items(row))
assert labels == ['United States'], labels
assert 'Albania' not in labels, labels

# Repair path must derive canonical/filter country from role_location first.
role_items = parse_location_items('Remote from US', source='current_role_location_field', evidence='Remote from US')
assert legacy_location_text(role_items) == 'United States'

location_py = Path('portal/services/location.py').read_text()
assert 'role_first_locations=parse_location_items(new_role' in location_py
assert 'before trusting persisted/structured arrays' in location_py
assert "ps.country_repair_version='0.11.2'" in Path('portal/tasks.py').read_text()

views_py = Path('portal/views.py').read_text()
assert "field=='country' and getattr(getattr(qs,'model',None),'__name__','')=='Opportunity'" in views_py
assert 'role_condition=_country_condition(\'role_location\',values)' in views_py
assert 'record_location_items(record)' in views_py

migration = Path('portal/migrations/0141_v0112_opportunity_location_tokens.py').read_text()
assert 'database_only_migration' in migration
assert 'ps.country_repair_version = \'\'' in migration

print('ScoutBox 0.11.2 regressions passed')
