from pathlib import Path

root = Path(__file__).resolve().parents[1]

def read(path):
    return (root / path).read_text(encoding='utf-8')

assert read('VERSION').strip() == '0.11.111'
assert read('RELEASE_ID').strip() == 'ScoutBox 0.11.111'
assert read('BUILD_INFO.txt').strip() == 'ScoutBox v0.11.111'
assert read('README.md').splitlines()[0] == '# ScoutBox 0.11.111'
assert (root / 'docs/RELEASE_NOTES_0.11.111.md').exists()

telemetry = read('templates/portal/telemetry.html')
assert "let best=resourceHits[0],bestDistance=Math.abs(best.x-canvasX)" in telemetry
assert "const distance=Math.abs(resourceHits[i].x-canvasX)" in telemetry
assert "ctx.setLineDash([])" in telemetry
assert "ctx.moveTo(best.x,g.top);ctx.lineTo(best.x,g.h-g.bottom)" in telemetry
assert "(row.at_export||row.at||'')" in telemetry
# Regression: do not reintroduce row-count/index based hover selection on the time-scaled chart.
assert "Math.round(ratio*Math.max(0,resourceHits.length-1))" not in telemetry

links = read('templates/portal/links.html')
assert 'data-align-search-table="tracking-table"' in links
assert 'data-align-search-col="1"' in links
# The generic alignment helper measures the selected table header's right edge.
base = read('templates/portal/base.html')
assert "width=Math.max(180,Math.round(t.right-r.left))" in base

mig = read('portal/migrations/0183_v011111_resource_hover_tracking_search.py')
assert "version='0.11.111'" in mig
assert '0182_v011110_tracking_invalid_link_message' in mig
print('ScoutBox 0.11.111 targeted regression checks passed')
