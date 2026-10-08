#!/usr/bin/env python3
"""ScoutBox 0.10.120 regression checks."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from portal.services.query_normalizer import normalize_generated_search_query as qn
from portal.services.location_values import location_title

assert qn('emulation engineer virtualization engineer Singapore hiring company careers "join our team"') == 'emulation virtualization engineer Singapore hiring company careers "join our team"'
assert qn('site:weworkremotely.com "technical writer"') == 'site:weworkremotely.com "technical writer"'
assert qn('firmware engineer embedded firmware engineer Singapore company careers') == 'firmware embedded engineer Singapore company careers'
assert location_title([{'label':'Bosnia and Herzegovina','source':'structured_jobposting','evidence':'[{"@type":"Country"}]'}]) == 'Location: Bosnia and Herzegovina'
print('ScoutBox 0.10.120 regressions passed')
