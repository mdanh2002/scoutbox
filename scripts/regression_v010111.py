from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from portal.services.location_values import parse_location_items, location_display_text
from portal.services.source_domains import expand_source_domains

labels = [x['label'] for x in parse_location_items('Remote from Europe, Ukraine', source='fixture')]
assert labels == ['Europe', 'Ukraine'], labels
assert location_display_text('Europe, Ukraine') == 'Europe, Ukraine'
assert 'Albania' not in labels
assert 'sg.indeed.com' in expand_source_domains('indeed.com', limit=8)
assert expand_source_domains('https://sg.indeed.com/jobs', limit=3)[0] == 'sg.indeed.com'

base = Path('templates/portal/base.html').read_text()
assert 'const releaseBusy=()=>{if(busyReleased)return;busyReleased=true;setListBusy(false)};' in base
assert 'window.setTimeout(()=>{try{controller.abort()}' in base
assert 'releaseBusy()' in base

opps = Path('templates/portal/opportunities.html').read_text()
assert 'value="lt3d"> ~ 3 days' in opps
assert 'record_locations_display' in opps

cold = Path('templates/portal/cold_contact.html').read_text()
assert 'hidden_lead_blacklist_valid_for_record' in cold
assert 'Company / domain' in cold
assert 'blacklistCompany||reviewDomain' in cold

fresh = Path('portal/services/freshness.py').read_text()
assert "'~ 3 days':3" in fresh
print('0.10.111 targeted regressions passed')
