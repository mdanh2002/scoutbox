from pathlib import Path

def read(path):
    return Path(path).read_text()

assert read('VERSION').strip() == '0.11.69'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.69'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.69'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.69'
stats = read('templates/portal/stats.html')
assert "hidden=Math.max(0,total-shown)" in stats
assert "' ('+hidden.toLocaleString()+' not shown)'" in stats
print('ScoutBox 0.11.69 regression checks passed')
