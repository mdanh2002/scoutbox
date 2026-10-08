from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:(ROOT/p).read_text()
assert read('VERSION').strip()=='0.11.65'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.65'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.65'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.65'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.65.md').exists()
stats=read('templates/portal/stats.html')
css=read('portal/static/portal/app.css')
# Regression: 0.11.64 declared layers const and then reassigned after filtering, aborting map init.
assert 'let layers=Array.isArray(statsWorldMapData?.layers)?statsWorldMapData.layers:[];' in stats
assert 'layers=layers.filter(layer=>allowedMapLayers.has' in stats
assert 'const zoomStops=[25,50,75,100,125,150,175,200,250,300,400,500,750,1000]' in stats
assert "zoomOut.addEventListener('click',()=>stepZoom(-1))" in stats
assert "zoomIn.addEventListener('click',()=>stepZoom(1))" in stats
assert '.topbar{border-bottom:0!important;}' in css
assert '.standalone-list-toolbar,.sticky-range-card{top:55px!important;}' in css
assert "allowedMapLayers=new Set(['opportunities','hidden_leads','contacts','blacklist'])" in stats
print('ScoutBox 0.11.65 regression checks passed')
