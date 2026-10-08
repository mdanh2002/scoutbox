#!/usr/bin/env python3
from pathlib import Path

root=Path(__file__).resolve().parents[1]

version=(root/'VERSION').read_text().strip()
assert version=='0.10.115', version
assert (root/'RELEASE_ID').read_text().strip()=='ScoutBox v0.10.115'
assert (root/'BUILD_INFO.txt').read_text().strip()=='ScoutBox v0.10.115'

loc=(root/'portal/services/location_values.py').read_text()
assert "'ASEAN'" in loc
assert "_FORBIDDEN_LOCATION_LABELS" in loc
assert "'Worldwide':" in loc  # known as an alias family, but blocked by normalizers
assert "LOCATION_CHOICES = [x for x in REGION_LABELS" in loc
assert "code') != 'WORLDWIDE'" in loc

location=(root/'portal/services/location.py').read_text()
assert '_jobicy_snapshot_role_location' in location
assert "return _result(items, jobicy_visible, 'jobicy_role_snapshot', jobicy_visible)" in location
assert "policy':'0.10.114 source-faithful recruiter location" in location
assert "if 'jobicy.com/jobs/'" in location

fresh=(root/'portal/services/freshness.py').read_text()
assert "if days < 3: return '< 3 days'" in fresh
assert "evergreen_flag" in fresh
assert "return 'Evergreen'" in fresh
assert "date recalc must not demote it" in fresh

tpl=(root/'templates/portal/opportunities.html').read_text()
assert '<select class="toolbar-uniform" name="read"' in tpl
assert 'value="evergreen"> Evergreen' in tpl
assert "age == 'Evergreen'" in tpl

cold=(root/'templates/portal/cold_contact.html').read_text()
assert '<select class="toolbar-uniform" name="read"' in cold
assert 'bulk-mark-control toolbar-uniform' in cold

contacts=(root/'templates/portal/contacts.html').read_text()
assert 'country-filter-select toolbar-uniform' in contacts
assert 'focus-filter-select toolbar-uniform' in contacts

css=(root/'portal/static/portal/app.css').read_text()
assert 'ScoutBox 0.10.114 — normalize all list-toolbar controls' in css
assert 'height:34px!important' in css

mig=(root/'portal/migrations/0134_v010114_source_location_worldwide_toolbar.py').read_text()
assert 'worldwide_persisted_location_blocked' in mig
assert 'repopulate_country_fields(fetch_pages=False)' in mig
mig2=(root/'portal/migrations/0135_v010114_evergreen_post_age.py').read_text()
assert 'Evergreen post-age repair' in mig2
assert "row.freshness_label='Evergreen'" in mig2

notes=(root/'docs/RELEASE_NOTES_0.10.115.md').read_text()
assert 'Evergreen' in notes and 'Worldwide' in notes and 'toolbar' in notes
print('0.10.115 targeted regressions passed')

# 0.10.115 hotfix: Django migrations must never perform external page fetch repairs.
from pathlib import Path as _Path
_mig134 = (_Path(__file__).resolve().parents[1] / 'portal/migrations/0134_v010114_source_location_worldwide_toolbar.py').read_text()
assert 'fetch_pages=True' not in _mig134, 'startup migration must not fetch external pages'
assert 'fetch_pages=False' in _mig134, 'startup migration must be DB-only'
_tasks = (_Path(__file__).resolve().parents[1] / 'portal/tasks.py').read_text()
assert "label='Repopulate country/location fields for 0.10.115'" in _tasks
assert "result=repopulate_country_fields(progress=progress,fetch_pages=True)" in _tasks, 'page-fetch repair must run only in background task'
assert "ps.country_repair_version='0.10.115'" in _tasks
print('0.10.115 startup-safe repair regressions passed')
