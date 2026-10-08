from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(name): return (ROOT/name).read_text()
assert read('VERSION').strip() == '0.11.70'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.70'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.70'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.70'
css=read('portal/static/portal/app.css')
assert '.stats-map-record-popover-label>span:first-child' in css
assert '.stats-map-record-popover-id{flex:0 0 auto;}' in css
stats=read('templates/portal/stats.html')
assert "id.textContent=' #'+recordId" in stats
print('ScoutBox 0.11.70 regression checks passed')
