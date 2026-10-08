from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:(ROOT/p).read_text()
assert read('VERSION').strip()=='0.11.66'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.66'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.66'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.66'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.66.md').exists()
stats=read('templates/portal/stats.html')
views=read('portal/views.py')
css=read('portal/static/portal/app.css')
assert 'Some items may be hidden due to insufficient location data.' in stats
assert "mapped_count=sum(max(1,int(x.get('count') or 1)) for x in displayed)" in views
assert "a.title=String(item.label||'Record')" in stats
assert 'min-width:290px;max-width:min(440px' in css
assert 'addedRecords' in stats and 'pointRecords' in stats
print('ScoutBox 0.11.66 regression checks passed')
