"""ScoutBox 0.11.1 regression checks."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portal.services.query_normalizer import split_multi_site_search_queries, normalize_generated_search_query

raw='site:facebook.com site:ashbyhq.com "emulation engineer" hardware interfaces'
parts=split_multi_site_search_queries(raw)
assert parts == [
    'site:facebook.com "emulation engineer" hardware interfaces',
    'site:ashbyhq.com "emulation engineer" hardware interfaces',
], parts
for q in parts:
    assert q.lower().count('site:') == 1, q
    assert '"emulation engineer"' in q, q

assert normalize_generated_search_query('emulation engineer virtualization engineer Singapore hiring company careers "join our team"') == 'emulation virtualization engineer Singapore hiring company careers "join our team"'

base=Path('templates/portal/base.html').read_text()
required=[
    'function clearListBusy()',
    'function reconcileListBusySoon()',
    "async function refreshAsyncList(form,href='',options={})",
    'silent=!!options.silent',
    'refreshAsyncList(form,window.location.href,{silent:true})',
    'window.addEventListener(\'pageshow\',clearListBusy)',
]
for token in required:
    assert token in base, token
assert 'function listNavigationBusy(){setListBusy(true);window.setTimeout(()=>{if(document.visibilityState===\'visible\')clearListBusy()},2500)}' in base
print('ScoutBox 0.11.1 regressions passed')
