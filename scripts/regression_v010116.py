from pathlib import Path
root=Path(__file__).resolve().parents[1]
assert (root/'VERSION').read_text().strip()=='0.10.116'
assert (root/'RELEASE_ID').read_text().strip()=='ScoutBox v0.10.116'
assert (root/'BUILD_INFO.txt').read_text().strip()=='ScoutBox v0.10.116'
loc=(root/'portal/services/location.py').read_text()
content=(root/'portal/services/content_quality.py').read_text()
assert 'def _snapshot_role_location' in loc
assert 'current_role_location_field' in loc
assert 'related remote jobs' in loc.lower()
assert 'def _role_location_scope' in content
assert 'related-job cards' in content or 'related jobs' in content.lower()
assert "label='Repopulate country/location fields for 0.10.116'" in (root/'portal/tasks.py').read_text()
# Migrations must not call source/page repair loops or HTTP clients.
for name in ['0134_v010114_source_location_worldwide_toolbar.py','0136_v010115_async_source_location_repair.py','0137_v010116_startup_safe_source_scoped_location.py']:
    text=(root/'portal/migrations'/name).read_text()
    assert 'requests.get' not in text
    assert 'fetch_target' not in text
    assert 'repopulate_country_fields(' not in text
print('0.10.116 targeted regressions passed')
