from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:(ROOT/p).read_text()
assert read('VERSION').strip()=='0.11.64'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.64'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.64'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.64'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.64.md').exists()
stats=read('templates/portal/stats.html')
css=read('portal/static/portal/app.css')
assert 'function pointTip(' not in stats
assert "btn.className='stats-map-marker stats-map-marker-'" in stats
assert "foot.textContent='Total records: '+total.toLocaleString()" in stats
assert "items.slice(0,5).forEach" in stats
assert 'stats-map-record-popover-total' in stats and '.stats-map-record-popover-total{' in css
assert 'ScoutBox 0.11.64 — click-first Global Activity Map record panel.' in css
assert "allowedMapLayers=new Set(['opportunities','hidden_leads','contacts','blacklist'])" in stats
assert "if(!allowedMapLayers.has(String(layer&&layer.key||'')))return" in stats
print('ScoutBox 0.11.64 regression checks passed')
